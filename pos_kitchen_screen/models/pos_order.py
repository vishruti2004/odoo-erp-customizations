from odoo import api, fields, models

READINESS = [
    ("no_items", "No kitchen items"), ("in_progress", "In progress"),
    ("partial_ready", "Partially ready"), ("ready", "Ready"), ("served", "Served"),
]


class PosOrder(models.Model):
    _inherit = "pos.order"

    kitchen_priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium", required=True,
        help="Chosen at the Point of Sale. The kitchen screens show high priority orders first.")
    prep_order_ids = fields.One2many("pos.prep.order", "pos_order_id", string="Preparation Tickets")
    kitchen_readiness = fields.Selection(
        READINESS, compute="_compute_kitchen_readiness", store=True, default="no_items")
    kitchen_station_status = fields.Json(compute="_compute_kitchen_readiness", store=True)
    kitchen_ready_at = fields.Datetime(readonly=True, copy=False)

    @api.model
    def _load_pos_preparation_data_fields(self):
        return super()._load_pos_preparation_data_fields() + [
            "kitchen_readiness", "kitchen_station_status", "kitchen_ready_at"]

    #  readiness
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
                lambda l: l.quantity - l.cancelled > 0 and l.state_ids)
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
            ready = sum(1 for s in states if s._kitchen_is_ready())
            if all(s.stage_id.stage_type == "done" for s in states):
                order.kitchen_readiness = "served"
            elif ready == len(states):
                order.kitchen_readiness = "ready"
            elif ready:
                order.kitchen_readiness = "partial_ready"
            else:
                order.kitchen_readiness = "in_progress"

    def set_kitchen_priority(self, priority):
        if priority not in ("low", "medium", "high"):
            return False
        self.write({"kitchen_priority": priority})
        self.env["pos.prep.order"].search([
            ("pos_order_id", "in", self.ids), ("priority", "!=", priority),
        ])._kitchen_apply_priority(priority)
        return True

    def _kitchen_readiness_snapshot(self):
        return {order.id: order.kitchen_readiness for order in self}

    def _kitchen_after_state_change(self, before):
        for order in self.filtered(lambda o: o.config_id.kitchen_advanced):
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

    #  native hook
    def _process_preparation_changes(self, options):
        self.ensure_one()
        if not self.config_id.kitchen_advanced:
            return super()._process_preparation_changes(options)

        Line = self.env["pos.prep.line"]
        domain = [("prep_order_id.pos_order_id", "=", self.id)]
        before = Line.search(domain)
        had_tickets = bool(before)
        snapshot = {
            l.id: {"qty": l.quantity, "cancelled": l.cancelled, "note": l.internal_note} for l in before}
        live_qty = {}
        for line in before:
            live_qty[line.pos_order_line_uuid] = live_qty.get(line.pos_order_line_uuid, 0.0) \
                + line.quantity - line.cancelled
        readiness_before = self._kitchen_readiness_snapshot()

        result = super()._process_preparation_changes(options)

        after = Line.search(domain)
        new_lines = after - before
        new_lines._kitchen_apply_routing()
        self.env["pos.prep.order"].search([
            ("pos_order_id", "=", self.id), ("priority", "!=", self.kitchen_priority),
        ])._kitchen_apply_priority(self.kitchen_priority)
        self._kitchen_track_changes(after, new_lines, snapshot, live_qty, had_tickets)
        self._kitchen_after_state_change(readiness_before)

        if result.get("change") and new_lines:
            native = self.env["pos.prep.display"]._get_preparation_displays(self, result.get("category_ids") or [])
            states = self.env["pos.prep.state"].search([("prep_line_id", "in", new_lines.ids)])
            for display in states.stage_id.prep_display_id - native:
                display._send_load_orders_message(result.get("sound"), result.get("notification"), self.id)
        return result

    def _kitchen_track_changes(self, after, new_lines, snapshot, live_qty, had_tickets):
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
                if (line.internal_note or "[]") != (old["note"] or "[]"):
                    events.append((line, "note_changed", line.quantity - line.cancelled,
                                   line.quantity - line.cancelled))
            elif line in new_lines:
                previous = live_qty.get(line.pos_order_line_uuid)
                if previous is None:
                    events.append((line, "new_item", 0.0, line.quantity))
                else:
                    events.append((line, "qty_increased", previous, previous + line.quantity))
        for line, event, old_qty, new_qty in events:
            History.create({
                "prep_order_id": line.prep_order_id.id, "prep_line_id": line.id, "pos_order_id": self.id,
                "product_id": line.product_id.id, "event_type": event,
                "old_quantity": old_qty, "new_quantity": new_qty,
            })
            if had_tickets or event not in ("new_item",):
                line.write({"last_change_type": event, "last_change_at": now})
        after._kitchen_sync_performance()


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    kitchen_station_id = fields.Many2one(
        "pos.kitchen.station", string="Kitchen Station", ondelete="set null",
        help="Manual override of the station routing. Set it before sending the order to the kitchen.")

    @api.model
    def _load_pos_data_fields(self, *args, **kwargs):
        fields_list = super()._load_pos_data_fields(*args, **kwargs)
        return fields_list + ["kitchen_station_id"] if fields_list else fields_list
