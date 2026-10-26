import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from .kitchen_balancer import KitchenBalancer
from .pos_prep_state import WORKING_TYPES

_logger = logging.getLogger(__name__)

ASSIGNMENT_MODES = [("auto", "Automatic"), ("manual", "Manual")]


class PosPrepLine(models.Model):
    _name = "pos.prep.line"
    _inherit = ["pos.prep.line", "pos.kitchen.access.mixin"]

    station_id = fields.Many2one("pos.kitchen.station", string="Kitchen Station", ondelete="set null", index=True)
    assigned_chef_id = fields.Many2one("pos.kitchen.chef", string="Assigned Chef", ondelete="set null", index=True)
    last_change_type = fields.Selection([
        ("none", "None"), ("qty_increased", "Quantity increased"),
        ("qty_decreased", "Quantity decreased"), ("cancelled", "Cancelled"),
        ("reprep", "Re-prepare"),
    ], default="none")
    last_change_at = fields.Datetime()
    change_text = fields.Char(help="What the waiter changed on the item, shown on the ticket.")
    change_pending = fields.Boolean(help="The change was not acknowledged by the kitchen yet.")
    moved_from = fields.Char(help="Name of the station the item was moved from (overflow / reassignment).")
    started_at = fields.Datetime(help="Set when work starts (chef assigned or item moved/crossed off). "
                                      "The native prep line has no equivalent field.")
    completed_at = fields.Datetime(help="Set when the item becomes ready.")
    state_ids = fields.One2many("pos.prep.state", "prep_line_id", string="States")
    station_assignment = fields.Selection(
        ASSIGNMENT_MODES, string="Station chosen",
        help="Automatic: routing / workload balancing. Manual: set by the cashier or moved by the kitchen; "
             "the automatic assignment never changes it.")
    chef_assignment = fields.Selection(
        ASSIGNMENT_MODES, string="Chef chosen",
        help="Automatic: given by the workload balancing, the item can still be moved or given to another chef. "
             "Manual: chosen or confirmed by a chef / manager; the automatic assignment never changes it "
             "unless it is explicitly requested.")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        routed = self.browse()
        balancers = {}
        for line in lines:
            config = line.prep_order_id.pos_order_id.config_id
            if not config.kitchen_advanced or line.pos_order_line_id.combo_line_ids:
                continue
            if self.env.context.get("kitchen_split"):
                # part of a line split between chefs: station and chef come with the values
                routed |= line
                continue
            override = line.pos_order_line_id.kitchen_station_id
            balancer = None
            if config._kitchen_auto():
                balancer = balancers.get(config.id) or balancers.setdefault(
                    config.id, KitchenBalancer(self.env, config, exclude_lines=lines))
            plan = []
            if balancer is not None and not override and not line.cancelled:
                plan = self.env["pos.kitchen.station"]._kitchen_plan_stations(
                    config, line.product_id, line.quantity, balancer)
            if plan:
                # the units are shared between the stations: one line per station (same ticket, same order line)
                line.write({"station_id": plan[0][0].id, "station_assignment": "auto", "quantity": plan[0][1]})
                for station, units in plan[1:]:
                    # the copy is logged in the performance report by its own create (kitchen_split)
                    line.with_context(kitchen_split=True).copy({
                        "quantity": units, "station_id": station.id, "station_assignment": "auto"})
                routed |= line
                continue
            station = self.env["pos.kitchen.station"]._kitchen_find_station(
                config, line.product_id, override, qty=line.quantity - line.cancelled, balancer=balancer)
            if station:
                manual = bool(override) and station == override
                if manual and balancer is not None:
                    # keep the snapshot right for the next items of the batch
                    qty = line.quantity - line.cancelled
                    balancer.commit(station, None, qty * station._kitchen_item_minutes(line.product_id, station), qty)
                line.write({"station_id": station.id, "station_assignment": "manual" if manual else "auto"})
            routed |= line
        if routed:
            self.env["pos.kitchen.performance"]._log_prep_lines(routed)
        return lines

    #  routing
    def _kitchen_apply_routing(self):
        """Keep the states of the routed lines only on the display of their station."""
        State = self.env["pos.prep.state"]
        for line in self:
            station = line.station_id
            if not station or line.pos_order_line_id.combo_line_ids:
                continue
            display = station.prep_display_id
            states = State.search([("prep_line_id", "=", line.id)])
            keep = states.filtered(lambda s: s.stage_id.prep_display_id == display)
            (states - keep).unlink()
            if not keep and display.stage_ids:
                State.create({"prep_line_id": line.id, "stage_id": display.stage_ids[0].id})

    #  performance log
    def _kitchen_sync_performance(self):
        Perf = self.env["pos.kitchen.performance"].sudo()
        now = fields.Datetime.now()
        cleared = self.browse()
        for line in self:
            perf = Perf.search([("prep_line_id", "=", line.id)], limit=1)
            states = line.state_ids
            if not states:
                continue
            ready = all(s._kitchen_is_ready() for s in states)
            if ready and line.change_pending:
                # the item is ready again: the change / re-prepare banner has been dealt with
                line_changes = {"change_pending": False}
                if line.last_change_type == "reprep":
                    line_changes.update(last_change_type="none", change_text=False)
                line.write(line_changes)
                cleared |= line
            if not perf:
                continue
            done = all(s.stage_id.stage_type == "done" for s in states)
            started = bool(line.assigned_chef_id and line.chef_assignment != "auto") or any(
                s.stage_id.stage_type != "todo" or not s.todo for s in states)
            vals = {}
            if started and not perf.started_at:
                vals["started_at"] = now
            if ready and not perf.ready_at:
                vals["ready_at"] = now
            elif not ready and perf.ready_at:
                vals["ready_at"] = False
            if done and not perf.served_at:
                vals["served_at"] = now
            elif not done and perf.served_at:
                vals["served_at"] = False
            if perf.cancelled_qty != line.cancelled:
                vals["cancelled_qty"] = line.cancelled
            if perf.qty != line.quantity:
                vals["qty"] = line.quantity
            station = line.station_id or states[:1].stage_id.prep_display_id.station_ids[:1]
            if station and perf.station_id != station:
                vals["station_id"] = station.id
            if perf.chef_id != line.assigned_chef_id:
                vals["chef_id"] = line.assigned_chef_id.id
            if vals:
                perf.write(vals)
                line_vals = {}
                if "started_at" in vals:
                    line_vals["started_at"] = vals["started_at"]
                if "ready_at" in vals:
                    line_vals["completed_at"] = vals["ready_at"]
                if line_vals:
                    line.write(line_vals)
        for display in cleared._kitchen_displays():
            display._notify("KITCHEN_LINE_CHANGES", [{
                "id": line.id, "change_pending": line.change_pending,
                "last_change_type": line.last_change_type, "change_text": line.change_text or "",
            } for line in cleared])

    def _kitchen_displays(self):
        return self.state_ids.stage_id.prep_display_id

    def _kitchen_history(self, move_type, **vals):
        return self.env["pos.kitchen.assignment.history"].sudo().create(
            dict(vals, move_type=move_type, order_name=self.prep_order_id.order_name))

    def _kitchen_flagged(self):
        lines = self.filtered(lambda l: l.prep_order_id.pos_order_id.config_id.kitchen_advanced)
        if not lines:
            self._kitchen_check_flag(self.prep_order_id.pos_order_id.config_id[:1])
        return lines

    #  automatic assignment
    def _kitchen_chef_movable(self):
        """The item may change station / chef without asking: nobody chose its chef by hand."""
        self.ensure_one()
        return not self.assigned_chef_id or self.chef_assignment == "auto"

    def _kitchen_station(self):
        self.ensure_one()
        return self.station_id or self._kitchen_displays().station_ids[:1]

    def _kitchen_pending_qty(self):
        """Quantity still to prepare, 0 when the item is ready / done / cancelled / a combo header."""
        self.ensure_one()
        qty = self.quantity - self.cancelled
        if qty <= 0 or self.pos_order_line_id.combo_line_ids or not self.state_ids:
            return 0.0
        if not all(s.todo and s.stage_id.stage_type in WORKING_TYPES for s in self.state_ids):
            return 0.0
        return qty

    def _kitchen_auto_assign(self, force=False, keep_eligible=False, actor=None, reason=False, split=True):
        """Give the pending items to the eligible chef with the lowest projected workload (fair turn on ties).

        force: also re-pick items that already have a chef, manual ones included (explicit request).
        keep_eligible: keep the current chef when he can still cook the item (on shift, on the station).
        split: a line of several units may be shared by several chefs (quantity wise). Off while the item
        is being moved to another stage.
        Returns {"assigned": {line id: chef id}, "skipped": [line ids], "unassigned": [line ids]}.
        An item for which no eligible chef exists keeps its station, stays unassigned (Take / Assign chef
        remain available) and the kitchen screen shows a warning: it is never skipped silently.
        """
        changed, modes, skipped = {}, {}, []
        unassigned = self.browse()
        split_orders = self.env["pos.order"]
        history_vals = []
        by_config = defaultdict(lambda: self.browse())
        for line in self:
            config = line.prep_order_id.pos_order_id.config_id
            if config and config._kitchen_auto():
                by_config[config] |= line
            else:
                skipped.append(line.id)
        priority = {"high": 0, "medium": 1, "low": 2}
        for config, lines in by_config.items():
            balancer = KitchenBalancer(self.env, config)
            for line in lines.sorted(lambda l: (priority.get(l.prep_order_id.priority, 1), l.id)):
                qty = line._kitchen_pending_qty()
                station = line._kitchen_station()
                previous = line.assigned_chef_id
                if not qty or not station or (previous and not force and not keep_eligible) \
                        or (line.chef_assignment == "manual" and not force):
                    skipped.append(line.id)
                    continue
                minutes = qty * station._kitchen_item_minutes(line.product_id, station)
                eligible = balancer.eligible_chefs(station, line.product_id)
                if keep_eligible and previous and previous in eligible:
                    skipped.append(line.id)
                    continue
                if previous:
                    # the item is part of the current chef's load: compare without it
                    balancer.release(None, previous, minutes, qty)
                # quantity wise: every unit of the line is given to a chef, units of one chef stay together
                plan = line._kitchen_plan_units(balancer, station, qty, minutes, split=split and not keep_eligible)
                if not plan:
                    if previous:
                        balancer.commit(None, previous, minutes, qty)
                    unassigned |= line
                    continue
                parts = line._kitchen_split_by_chef(plan, station) if len(plan) > 1 else [(line, plan[0][0])]
                if len(parts) > 1:
                    split_orders |= line.prep_order_id.pos_order_id
                for part, chef in parts:
                    if part == line and chef == previous:
                        continue
                    if part == line:
                        part.write({"assigned_chef_id": chef.id, "chef_assignment": "auto"})
                    history_vals.append(dict(
                        move_type="auto_assign", order_name=part.prep_order_id.order_name,
                        prep_line_id=part.id, pos_order_id=part.prep_order_id.pos_order_id.id,
                        product_id=part.product_id.id, previous_chef_id=previous.id if part == line else False,
                        new_chef_id=chef.id, previous_station_id=station.id, new_station_id=station.id,
                        changed_by_chef_id=actor.id if actor else False,
                        reason=reason or part._kitchen_auto_reason(station, balancer.chef_load[chef.id])))
                    changed[part.id] = chef.id
                    modes[part.id] = "auto"
        if history_vals:
            self.env["pos.kitchen.assignment.history"].sudo().create(history_vals)
        changed_lines = self.browse(list(changed))
        if changed_lines:
            changed_lines._kitchen_sync_performance()
            for display in changed_lines._kitchen_displays():
                display._notify("CHEF_ASSIGNED", {"assignments": changed, "modes": modes})
                display._notify("WORKLOAD_CHANGED", {})
        for order in split_orders:
            # the new parts of the split lines must be loaded by the screens
            for display in changed_lines.filtered(lambda l: l.prep_order_id.pos_order_id == order)._kitchen_displays():
                display._send_load_orders_message(False, None, order.id)
        unassigned._kitchen_warn_no_chef()
        return {"assigned": changed, "skipped": skipped, "unassigned": unassigned.ids}

    def _kitchen_plan_units(self, balancer, station, qty, minutes, split=True):
        """[(chef, units)] for the line. Whole units are given one by one to the best chef (the snapshot is
        updated after each unit, so the fair turn and the workload spread the quantity); a line that cannot
        be split (decimal quantity, combo, partly cancelled, started) goes to one chef. [] = no chef."""
        self.ensure_one()
        product = self.product_id
        units = int(qty) if split and self._kitchen_splittable(qty) else 0
        if units < 2:
            _station, chef, minutes = balancer.pick(product, qty, station)
            if not chef:
                return []
            balancer.commit(None, chef, minutes, qty)
            return [(chef, qty)]
        unit_minutes = minutes / qty
        plan = {}
        for _unit in range(units):
            _station, chef, _minutes = balancer.pick(product, 1.0, station)
            if not chef:
                break
            balancer.commit(None, chef, unit_minutes, 1.0)
            plan[chef] = plan.get(chef, 0.0) + 1.0
        plan = list(plan.items())
        rest = qty - sum(units for _chef, units in plan)
        if plan and rest > 0:  # never lose quantity: what could not be planned stays with the first chef
            plan[0] = (plan[0][0], plan[0][1] + rest)
            balancer.commit(None, plan[0][0], rest * unit_minutes, rest)
        return plan

    def _kitchen_splittable(self, qty):
        self.ensure_one()
        return (qty > 1 and float(qty).is_integer() and not self.cancelled
                and not self.pos_order_line_id.combo_line_ids and not self.pos_order_line_id.combo_parent_id
                and all(s.todo and s.stage_id.stage_type == "todo" for s in self.state_ids))

    def _kitchen_split_by_chef(self, plan, station):
        """Split the line in one line per chef of ``plan`` [(chef, units)]: the line keeps the first part,
        a copy (same ticket, same order line, same stage) is created for each other chef.
        Returns [(line, chef)]."""
        self.ensure_one()
        Perf = self.env["pos.kitchen.performance"].sudo()
        sent_at = Perf.search([("prep_line_id", "=", self.id)], limit=1).sent_at
        (first_chef, first_units), others = plan[0], plan[1:]
        parts = [(self, first_chef)]
        for chef, units in others:
            part = self.with_context(kitchen_split=True).copy({
                "quantity": units, "cancelled": 0, "station_id": station.id,
                "station_assignment": self.station_assignment, "assigned_chef_id": chef.id,
                "chef_assignment": "auto", "moved_from": self.moved_from,
            })
            for state in self.state_ids:
                state.copy({"prep_line_id": part.id})
            if sent_at:
                Perf.search([("prep_line_id", "=", part.id)]).write({"sent_at": sent_at})
            parts.append((part, chef))
        self.write({"quantity": first_units, "assigned_chef_id": first_chef.id, "chef_assignment": "auto"})
        return parts

    def _kitchen_auto_reason(self, station, chef_load):
        if station.workload_metric == "time":
            return _("Automatic (Time Wise): chef workload %(value)s min", value=round(chef_load["minutes"], 1))
        return _("Automatic (Item Wise): chef workload %(value)g item(s)", value=chef_load["items"])

    def _kitchen_warn_no_chef(self):
        """Visible warning for the items the automatic assignment could not give to a chef."""
        for line in self:
            _logger.warning("Kitchen auto-assignment: no eligible chef for prep line %s (%s, station %s)",
                            line.id, line.product_id.display_name, line._kitchen_station().name)
        for display in self._kitchen_displays():
            lines = self.filtered(lambda l: display in l._kitchen_displays())
            names = ", ".join(dict.fromkeys(
                "%s (%s)" % (l.product_id.display_name, l._kitchen_station().name or display.name) for l in lines))
            display._notify("KITCHEN_WARNING", {"message": _(
                "No chef available for %s. Please assign manually.", names)})

    def _kitchen_auto_rebalance_stations(self, actor_chef_id=False):
        """Move the items that are not started and have no manually chosen chef to the station with the
        lowest projected workload (only stations handling their category). Returns the moved line ids."""
        moves = defaultdict(lambda: self.browse())
        for config, lines in self.grouped(lambda l: l.prep_order_id.pos_order_id.config_id).items():
            if not config._kitchen_auto():
                continue
            balancer = KitchenBalancer(self.env, config)
            for line in lines:
                qty = line._kitchen_pending_qty()
                current = line._kitchen_station()
                if not qty or not line._kitchen_chef_movable() \
                        or any(s.stage_id.stage_type != "todo" for s in line.state_ids):
                    continue
                stations = balancer.candidate_stations(line.product_id)
                if len(stations) < 2 or current not in stations:
                    continue
                own = qty * current._kitchen_item_minutes(line.product_id, current)
                balancer.release(current, line.assigned_chef_id if line.chef_assignment == "auto" else None, own, qty)
                target, chef, minutes = balancer.pick(line.product_id, qty, stations)
                if not target or target == current:
                    balancer.commit(current, line.assigned_chef_id if line.chef_assignment == "auto" else None,
                                    own, qty)
                    continue
                balancer.commit(target, chef, minutes, qty)
                moves[target] |= line
        moved = []
        for target, lines in moves.items():
            result = lines.with_context(kitchen_auto_move=True).reassign(
                target.id, _("Automatic workload balancing"), actor_chef_id)
            moved += result["moved"]
        return moved

    def _kitchen_auto_overflow(self):
        """After the workload of these items changed (ready, done, re-prepared...): in Dynamic Automatic mode
        the overloaded stations of the company send their excess to stations that now have free capacity.
        Never blocks the kitchen action that triggered it."""
        companies = self.prep_order_id.pos_order_id.config_id.filtered(lambda c: c._kitchen_auto()).company_id
        for company in companies:
            try:
                with self.env.cr.savepoint():
                    self.env["pos.kitchen.station"]._kitchen_auto_resolve_overload_for(company)
            except Exception:
                _logger.exception("Kitchen automatic overflow failed")

    def kitchen_auto_assign(self, rebalance_station=False, actor_chef_id=False):
        """RPC (called with [line_ids, rebalance_station, actor_chef_id]): explicit request from the kitchen
        to choose the station (optional) and the chef automatically, manual choices included."""
        self._kitchen_check_manager()
        lines = self._kitchen_flagged()
        actor = self._kitchen_get_actor(actor_chef_id)
        configs = lines.prep_order_id.pos_order_id.config_id
        if not any(c._kitchen_auto() for c in configs):
            raise UserError(_("Automatic assignment is not enabled for this Point of Sale."))
        moved = lines._kitchen_auto_rebalance_stations(actor_chef_id) if rebalance_station else []
        lines.invalidate_recordset()
        # the moved items already got a chef of their new station (reassign): no second assignment record
        result = lines.filtered(lambda l: l.id not in moved)._kitchen_auto_assign(
            force=True, actor=actor, reason=_("Automatic, requested from the kitchen screen"))
        for line in lines.filtered(lambda l: l.id in moved and l.assigned_chef_id):
            result["assigned"][line.id] = line.assigned_chef_id.id
        result["moved"] = moved
        return result

    #  chef assignment
    def assign_chef(self, chef_id, actor_chef_id=False, reason=False):
        lines = self._kitchen_flagged()
        actor = self._kitchen_get_actor(actor_chef_id)
        chef = self.env["pos.kitchen.chef"].browse(int(chef_id)).exists() if chef_id else self.env["pos.kitchen.chef"]
        if chef and (not chef.active or chef.company_id not in self.env.companies):
            raise AccessError(_("This chef cannot be assigned."))
        if not self._kitchen_is_manager():
            own = self._kitchen_user_chef()
            if not own or chef != own:
                raise AccessError(_("You can only take items for yourself."))
            actor = own
        if chef:
            chef._kitchen_check_on_shift()
        changed, not_cooked = {}, 0
        for line in lines:
            if chef and not chef._kitchen_can_cook(line.product_id):
                not_cooked += 1
                continue
            config = line.prep_order_id.pos_order_id.config_id
            station = line.station_id or line._kitchen_displays().station_ids[:1]
            if chef and config.kitchen_strict_chef_station and chef.station_ids and station \
                    and station not in chef.station_ids:
                raise AccessError(_("%(chef)s is not assigned to %(station)s.",
                                    chef=chef.name, station=station.name))
            previous = line.assigned_chef_id
            if previous == chef:
                if chef and line.chef_assignment == "auto":
                    # the chef takes / confirms the item he was given automatically: it is now his choice
                    line.chef_assignment = "manual"
                    changed[line.id] = chef.id
                continue
            line.write({"assigned_chef_id": chef.id, "chef_assignment": "manual" if chef else False})
            line._kitchen_history(
                "reassign" if previous and chef else "assign",
                prep_line_id=line.id, pos_order_id=line.prep_order_id.pos_order_id.id,
                product_id=line.product_id.id, previous_chef_id=previous.id, new_chef_id=chef.id,
                previous_station_id=line.station_id.id, new_station_id=line.station_id.id,
                changed_by_chef_id=actor.id, reason=reason)
            changed[line.id] = chef.id or False
        if not_cooked and not changed and chef:
            raise AccessError(_("%s does not handle this category.", chef.name))
        changed_lines = lines.filtered(lambda l: l.id in changed)
        changed_lines._kitchen_sync_performance()
        for display in changed_lines._kitchen_displays():
            display._notify("CHEF_ASSIGNED", {
                "assignments": changed, "modes": {lid: "manual" if cid else False for lid, cid in changed.items()}})
            display._notify("WORKLOAD_CHANGED", {})
        return True

    #  re-prepare: an item that is ready goes back to the first stage of its screen
    def kitchen_reprepare(self, reason_type, reason=False, actor_chef_id=False):
        """RPC (called with [line_ids, reason_type, reason, actor_chef_id])."""
        lines = self._kitchen_flagged()
        actor = self._kitchen_get_actor(actor_chef_id)
        History = self.env["pos.kitchen.item.history"]
        labels = dict(History._fields["reason_type"]._description_selection(self.env))
        if reason_type not in labels:
            raise UserError(_("Select a reason."))
        reason = (reason or "").strip()
        if reason_type == "other" and not reason:
            raise UserError(_("Enter a reason."))
        text = reason if reason_type == "other" else labels[reason_type]
        orders = lines.prep_order_id.pos_order_id
        before = orders._kitchen_readiness_snapshot()
        now = fields.Datetime.now()
        moved, skipped = self.browse(), self.browse()
        for line in lines:
            states = line.state_ids
            if (line.quantity - line.cancelled) <= 0 or not states \
                    or not all(s.stage_id.stage_type == "ready" for s in states):
                skipped |= line
                continue
            for state in states:
                first = state.stage_id.prep_display_id.stage_ids[:1]
                state.write({"stage_id": first.id, "todo": True})
            line.write({
                "last_change_type": "reprep", "last_change_at": now, "change_pending": True,
                "change_text": _("Re-prepare: %s", text),
            })
            History.sudo().create({
                "prep_line_id": line.id, "pos_order_id": line.prep_order_id.pos_order_id.id,
                "order_name": line.prep_order_id.order_name, "product_id": line.product_id.id,
                "event_type": "reprep", "old_quantity": line.quantity - line.cancelled,
                "new_quantity": line.quantity - line.cancelled, "reason_type": reason_type, "reason": text,
                "chef_id": actor.id, "station_id": line.station_id.id,
            })
            moved |= line
        moved._kitchen_sync_performance()
        # Dynamic Automatic: keep the automatic chef if still eligible, else (or without chef) choose one
        moved.filtered(lambda l: l.chef_assignment == "auto" or not l.assigned_chef_id)._kitchen_auto_assign(
            keep_eligible=True, actor=actor, reason=_("Automatic after re-prepare"))
        moved._kitchen_auto_overflow()
        orders._kitchen_after_state_change(before)
        for order in moved.prep_order_id.pos_order_id:
            order_lines = moved.filtered(lambda l: l.prep_order_id.pos_order_id == order)
            for display in order_lines._kitchen_displays():
                display._send_load_orders_message(True, _("Re-prepare: order %s", order.tracking_number or order.name), order.id)
                display._notify("WORKLOAD_CHANGED", {})
        return {"moved": moved.ids, "skipped": skipped.ids}

    #  move items to another station
    def reassign(self, target_station_id, reason=False, actor_chef_id=False):
        if not self.env.context.get("kitchen_auto_move"):
            self._kitchen_check_manager(_("Only kitchen managers can move items."))
        lines = self._kitchen_flagged()
        target = self.env["pos.kitchen.station"].browse(int(target_station_id)).exists()
        if not target or not target.active:
            raise UserError(_("Station not found."))
        actor = self._kitchen_get_actor(actor_chef_id)
        all_orders = lines.prep_order_id.pos_order_id
        before = all_orders._kitchen_readiness_snapshot()
        t_display = target.prep_display_id
        t_first = t_display.stage_ids[:1]
        moved, skipped, rechef = self.browse(), self.browse(), self.browse()
        source_state_ids = defaultdict(list)
        source_displays = self.env["pos.prep.display"]
        notify_orders = self.env["pos.order"]
        source_names = []
        for line in lines:
            config = line.prep_order_id.pos_order_id.config_id
            if (target.pos_config_ids and config not in target.pos_config_ids) or target.company_id != config.company_id:
                raise UserError(_("%(station)s is not available for this Point of Sale.", station=target.name))
            source = line.station_id or line._kitchen_displays().station_ids[:1]
            src_states = line.state_ids.filtered(lambda s: s.stage_id.prep_display_id != t_display)
            eligible = (
                src_states
                and target._kitchen_handles(line.product_id)
                and (line.quantity - line.cancelled) > 0
                and line._kitchen_chef_movable()
                and all(s.todo and s.stage_id.stage_type == "todo" for s in src_states)
            )
            if not eligible:
                skipped |= line
                continue
            for state in src_states:
                source_displays |= state.stage_id.prep_display_id
                source_state_ids[state.stage_id.prep_display_id.id].append(state.id)
            if line.state_ids.filtered(lambda s: s.stage_id.prep_display_id == t_display):
                src_states.unlink()
            else:
                src_states.write({"stage_id": t_first.id, "todo": True})
            vals = {
                "station_id": target.id, "moved_from": source.name or False,
                "station_assignment": "auto" if self.env.context.get("kitchen_auto_move") else "manual",
            }
            if line.assigned_chef_id:
                # automatic chef of the old station: a chef of the new station is chosen below
                vals.update(assigned_chef_id=False, chef_assignment=False)
            rechef |= line  # no chef at the destination yet (Dynamic Automatic picks one, Manual: none)
            line.write(vals)
            line._kitchen_history(
                "station_move", prep_line_id=line.id, pos_order_id=line.prep_order_id.pos_order_id.id,
                product_id=line.product_id.id, previous_station_id=source.id, new_station_id=target.id,
                changed_by_chef_id=actor.id, reason=reason)
            moved |= line
            if source and source.name not in source_names:
                source_names.append(source.name)
            notify_orders |= line.prep_order_id.pos_order_id
        moved._kitchen_sync_performance()
        if rechef:
            rechef._kitchen_auto_assign(actor=actor, reason=_("Automatic after move to %s", target.name))
        all_orders._kitchen_after_state_change(before)
        for display in source_displays:
            display._notify("STATION_REASSIGNED", {"state_ids": source_state_ids[display.id]})
            display._notify("WORKLOAD_CHANGED", {})
        if moved:
            for order in notify_orders:
                t_display._send_load_orders_message(True, _("Items moved from %s", ", ".join(source_names) or "-"), order.id)
            t_display._notify("WORKLOAD_CHANGED", {})
        return {"moved": moved.ids, "skipped": skipped.ids}