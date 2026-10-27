import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError


READINESS = [
    ("no_items", "No kitchen items"), ("in_progress", "In progress"),
    ("partial_ready", "Partially ready"), ("ready", "Ready"), ("served", "Served"),
]

class PosOrder(models.Model):
    _inherit = "pos.order"

    kitchen_priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium",
        help="Medium unless the cashier changes it on the Orders screen. The kitchen shows high priority orders first.")
    prep_order_ids = fields.One2many("pos.prep.order", "pos_order_id", string="Preparation Tickets")
    kitchen_readiness = fields.Selection(
        READINESS, compute="_compute_kitchen_readiness", store=True, default="no_items")
    kitchen_station_status = fields.Json(compute="_compute_kitchen_readiness", store=True)
    kitchen_ready_at = fields.Datetime(readonly=True, copy=False)

    @api.model
    def _load_pos_preparation_data_fields(self):
        return super()._load_pos_preparation_data_fields() + [
            "kitchen_readiness", "kitchen_station_status", "kitchen_ready_at"]

    @api.depends(
        "prep_order_ids.prep_line_ids.quantity",
        "prep_order_ids.prep_line_ids.cancelled",
        "prep_order_ids.prep_line_ids.state_ids.todo",
        "prep_order_ids.prep_line_ids.state_ids.stage_id",
        "prep_order_ids.prep_line_ids.state_ids.stage_id.stage_type",
    )
    def _compute_kitchen_readiness(self):
        for order in self:
            lines = order.prep_order_ids.prep_line_ids.filtered(
                lambda line: line.quantity - line.cancelled > 0 and line.state_ids)
            states = lines.state_ids
            per_display = {}
            for state in states:
                display = state.stage_id.prep_display_id
                info = per_display.setdefault(str(display.id), {
                    "name": display.station_ids[:1].name or display.name, "total": 0, "ready": 0})
                info["total"] += 1
                info["ready"] += 1 if state._kitchen_is_ready() else 0
            order.kitchen_station_status = per_display
            if not states:
                order.kitchen_readiness = "no_items"
                continue
            ready = sum(1 for state in states if state._kitchen_is_ready())
            if all(state.stage_id.stage_type == "done" for state in states):
                order.kitchen_readiness = "served"
            elif ready == len(states):
                order.kitchen_readiness = "ready"
            elif ready:
                order.kitchen_readiness = "partial_ready"
            else:
                order.kitchen_readiness = "in_progress"

    def write(self, vals):
        cancelled = self.browse()
        if vals.get("state") == "cancel":
            cancelled = self.filtered(lambda order: order.state != "cancel" and order.prep_order_ids)
        result = super().write(vals)
        for order in cancelled:
            for display in order.prep_order_ids._kitchen_displays():
                display._notify("POS_ORDER_DELETED", {"pos_order_ids": order.ids})
                display._notify("WORKLOAD_CHANGED", {})
        return result

    def set_kitchen_priority(self, priority):
        if priority not in ("low", "medium", "high"):
            return False
        self.write({"kitchen_priority": priority})
        self.env["pos.prep.order"].search([
            ("pos_order_id", "in", self.ids), ("priority", "!=", priority),
        ])._kitchen_apply_priority(priority)
        return True

    @api.model
    def get_kitchen_locked_ids(self, order_ids):
        orders = self.browse([order_id for order_id in order_ids if isinstance(order_id, int)]).exists()
        return orders.filtered(
            lambda order: order.config_id.kitchen_advanced and order.kitchen_readiness in ("ready", "served")).ids

    def _kitchen_readiness_snapshot(self):
        return {order.id: order.kitchen_readiness for order in self}

    def _kitchen_after_state_change(self, before):
        for order in self.filtered(lambda order: order.config_id.kitchen_advanced):
            old = before.get(order.id)
            new = order.kitchen_readiness
            if old == new:
                continue
            vals = {}
            if new in ("ready", "served") and old not in ("ready", "served"):
                vals["kitchen_ready_at"] = fields.Datetime.now()
            elif new not in ("ready", "served") and order.kitchen_ready_at:
                vals["kitchen_ready_at"] = False 
            if vals:
                order.sudo().write(vals)
            was_locked = old in ("ready", "served")
            is_locked = new in ("ready", "served")
            if was_locked != is_locked:
                order.config_id.sudo()._notify("KITCHEN_ORDER_LOCK", {"order_id": order.id, "locked": is_locked})
            displays = self.env["pos.prep.display"]._kitchen_displays_for_orders(order)
            payload = {
                "order_id": order.id, "readiness": new, "status": order.kitchen_station_status,
                "ready_at": fields.Datetime.to_string(order.kitchen_ready_at) if order.kitchen_ready_at else False,
                "name": order.floating_order_name or order.tracking_number,
            }
            for display in displays:
                display._notify("KITCHEN_READINESS_CHANGED", payload)
                if new == "ready" and old != "ready":
                    display._notify("KITCHEN_ORDER_READY", payload)

    def _process_preparation_changes(self, options):
        self.ensure_one()
        if not self.config_id.kitchen_advanced:
            return super()._process_preparation_changes(options)

        Line = self.env["pos.prep.line"]
        domain = [("prep_order_id.pos_order_id", "=", self.id)]
        before = Line.search(domain)
        snapshot = {
            line.id: {"qty": line.quantity, "cancelled": line.cancelled} for line in before}
        live_qty = {}
        for line in before:
            live_qty[line.pos_order_line_uuid] = live_qty.get(line.pos_order_line_uuid, 0.0) \
                + line.quantity - line.cancelled
        readiness_before = self._kitchen_readiness_snapshot()

        result = super()._process_preparation_changes(options)

        after = Line.search(domain)
        new_lines = after - before
        new_lines._kitchen_apply_routing()
        priority = self.kitchen_priority or "medium"
        self.env["pos.prep.order"].search([
            ("pos_order_id", "=", self.id), ("priority", "!=", priority),
        ])._kitchen_apply_priority(priority)
        self._kitchen_check_changeable(after, new_lines, snapshot, readiness_before)
        order_cancelled = bool(options.get("cancelled")) or not any(
            line.quantity - line.cancelled > 0 for line in after)
        self._kitchen_track_changes(after, new_lines, snapshot, live_qty, notify=not order_cancelled)
        touched = self._kitchen_merge_into_open_ticket(before, new_lines)
        if self.config_id._kitchen_auto():
            self._kitchen_run_auto_assign(new_lines.exists() | touched)
        self._kitchen_after_state_change(readiness_before)

        if result.get("change") and new_lines:
            native = self.env["pos.prep.display"]._get_preparation_displays(self, result.get("category_ids") or [])
            states = self.env["pos.prep.state"].search([("prep_line_id", "in", new_lines.ids)])
            for display in states.stage_id.prep_display_id - native:
                display._send_load_orders_message(result.get("sound"), result.get("notification"), self.id)
        return result

    def _kitchen_merge_into_open_ticket(self, before, new_lines):
        open_tickets = before.prep_order_id.filtered(lambda ticket: any(
            state.stage_id.stage_type in ("todo", "in_progress") for state in ticket.prep_line_ids.state_ids))
        if not open_tickets or not new_lines:
            return self.env["pos.prep.line"]
        ticket = open_tickets.sorted("id")[0]
        now = fields.Datetime.now()
        new_tickets = new_lines.prep_order_id
        touched = self.env["pos.prep.line"]
        for line in new_lines:
            if line.pos_order_line_id.combo_line_ids or line.pos_order_line_id.combo_parent_id:
                continue
            old = ticket.prep_line_ids.filtered(
                lambda existing: existing not in new_lines and existing.pos_order_line_uuid == line.pos_order_line_uuid
                and existing.quantity - existing.cancelled > 0
                and any(state.stage_id.stage_type in ("todo", "in_progress") for state in existing.state_ids))[:1]
            if old:
                before_qty = old.quantity - old.cancelled
                added = line.quantity
                self.env["pos.kitchen.item.history"].sudo().search(
                    [("prep_line_id", "=", line.id)]).write({"prep_line_id": old.id})
                self.env["pos.kitchen.performance"].sudo().search([("prep_line_id", "=", line.id)]).unlink()
                line.unlink()
                old.write({
                    "quantity": old.quantity + added, "last_change_type": "qty_increased", "last_change_at": now,
                    "change_text": _("Qty updated: %(old)g → %(new)g", old=before_qty, new=before_qty + added),
                    "change_pending": True,
                })
                old._kitchen_sync_performance()
                touched |= old
            else:
                line.write({"prep_order_id": ticket.id})
                touched |= line
        new_tickets.filtered(lambda ticket: not ticket.prep_line_ids).unlink()
        for display in touched.state_ids.stage_id.prep_display_id:
            display._send_load_orders_message(True, None, self.id)
        return touched

    def _kitchen_run_auto_assign(self, lines):
        lines = lines.filtered(lambda line: line.exists())
        if not lines:
            return
        try:
            with self.env.cr.savepoint():
                lines._kitchen_auto_assign()
                stations = lines.exists().station_id
                (stations | stations.mapped(lambda station: station._kitchen_compatible_stations()))\
                    ._kitchen_auto_resolve_overload(notify_unresolved=True)
        except Exception:
            for display in lines._kitchen_displays():
                display._notify("KITCHEN_WARNING", {"message": _(
                    "Automatic assignment failed for order %s. Please assign manually.",
                    self.tracking_number or self.name)})

    def _kitchen_check_changeable(self, after, new_lines, snapshot, readiness_before):
        def is_ready(line):
            return bool(line.state_ids) and all(state._kitchen_is_ready() for state in line.state_ids)

        ready_uuids = {line.pos_order_line_uuid for line in after if line not in new_lines and is_ready(line)}
        cancelled = [line for line in after if line.id in snapshot and line.cancelled > snapshot[line.id]["cancelled"]]
        fully_ready = readiness_before.get(self.id) in ("ready", "served")
        blocked = (
            (fully_ready and (new_lines or cancelled))
            or any(is_ready(line) for line in cancelled)
            or any(line.pos_order_line_uuid in ready_uuids for line in new_lines)
        )
        if blocked:
            raise UserError(_(
                "Order %s is ready in the kitchen and cannot be changed.",
                self.tracking_number or self.display_name))

    def _kitchen_track_changes(self, after, new_lines, snapshot, live_qty, notify=True):
        History = self.env["pos.kitchen.item.history"].sudo()
        now = fields.Datetime.now()
        events = []
        for line in after:
            if line.id in snapshot:
                old = snapshot[line.id]
                if line.cancelled > old["cancelled"]:
                    remainder = line.quantity - line.cancelled
                    events.append((line, "qty_decreased" if remainder > 0 else "cancelled",
                                   old["qty"] - old["cancelled"], remainder))
            elif line in new_lines:
                previous = live_qty.get(line.pos_order_line_uuid)
                if previous is not None:
                    events.append((line, "qty_increased", previous, previous + line.quantity))
                elif snapshot:
                    events.append((line, "added", 0.0, line.quantity))
        texts = {
            "qty_decreased": lambda old_qty, new_qty: _("Qty updated: %(old)g → %(new)g", old=old_qty, new=new_qty),
            "cancelled": lambda old_qty, new_qty: _("Item cancelled"),
            "qty_increased": lambda old_qty, new_qty: _("Qty updated: %(old)g → %(new)g", old=old_qty, new=new_qty),
            "added": lambda old_qty, new_qty: _("Item added"),
        }
        for line, event, old_qty, new_qty in events:
            History.create({
                "prep_line_id": line.id, "pos_order_id": self.id, "order_name": line.prep_order_id.order_name,
                "product_id": line.product_id.id, "event_type": event,
                "old_quantity": old_qty, "new_quantity": new_qty,
            })
            text = texts[event](old_qty, new_qty)
            pending = bool(line.state_ids) and not all(state._kitchen_is_ready() for state in line.state_ids)
            line.write({"last_change_type": event, "last_change_at": now,
                        "change_text": text, "change_pending": pending})
            if not notify:
                continue
            for display in line.state_ids.stage_id.prep_display_id:
                display._notify("ITEM_CHANGED", {
                    "order": line.prep_order_id.order_name, "product": line.product_id.display_name,
                    "text": text})
        after._kitchen_sync_performance()


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    kitchen_station_id = fields.Many2one(
        "pos.kitchen.station", string="Kitchen Station", ondelete="set null",
        help="Manual override of the station routing. Set it before sending the order to the kitchen.")
