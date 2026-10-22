from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class PosPrepLine(models.Model):
    _name = "pos.prep.line"
    _inherit = ["pos.prep.line", "pos.kitchen.access.mixin"]

    station_id = fields.Many2one("pos.kitchen.station", string="Kitchen Station", ondelete="set null", index=True)
    assigned_chef_id = fields.Many2one("pos.kitchen.chef", string="Assigned Chef", ondelete="set null", index=True)
    reprep_count = fields.Integer("Re-preparations", default=0)
    last_change_type = fields.Selection([
        ("none", "None"), ("new_item", "New item"), ("qty_increased", "Quantity increased"),
        ("qty_decreased", "Quantity decreased"), ("cancelled", "Cancelled"),
        ("note_changed", "Note changed"), ("reprep", "Re-prepare"),
    ], default="none")
    last_change_at = fields.Datetime()
    change_text = fields.Char(help="What the waiter changed on the item, shown on the ticket.")
    change_pending = fields.Boolean(help="The change was not acknowledged by the kitchen yet.")
    moved_from = fields.Char(help="Name of the station the item was moved from (overflow / reassignment).")
    started_at = fields.Datetime(help="Set when work starts (chef assigned or item moved/crossed off). "
                                      "The native prep line has no equivalent field.")
    completed_at = fields.Datetime(help="Set when the item becomes ready.")
    state_ids = fields.One2many("pos.prep.state", "prep_line_id", string="States")

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        routed = self.browse()
        for line in lines:
            config = line.prep_order_id.pos_order_id.config_id
            if not config.kitchen_advanced or line.pos_order_line_id.combo_line_ids:
                continue
            station = self.env["pos.kitchen.station"]._kitchen_find_station(
                config, line.product_id, line.pos_order_line_id.kitchen_station_id)
            if station:
                line.station_id = station
            routed |= line
        if routed:
            self.env["pos.kitchen.performance"]._log_prep_lines(routed)
        return lines

    #  routing
    def _kitchen_apply_routing(self):
       
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
        for line in self:
            perf = Perf.search([("prep_line_id", "=", line.id)], limit=1)
            states = line.state_ids
            if not perf or not states:
                continue
            ready = all(s._kitchen_is_ready() for s in states)
            done = all(s.stage_id.stage_type == "done" for s in states)
            started = bool(line.assigned_chef_id) or any(
                s.stage_id.stage_type != "todo" or not s.todo for s in states)
            vals = {}
            if ready and line.change_pending:
                line.change_pending = False
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
            if perf.reprep_count != line.reprep_count:
                vals["reprep_count"] = line.reprep_count
            if vals:
                perf.write(vals)
                line_vals = {}
                if "started_at" in vals:
                    line_vals["started_at"] = vals["started_at"]
                if "ready_at" in vals:
                    line_vals["completed_at"] = vals["ready_at"]
                if line_vals:
                    line.write(line_vals)

    def _kitchen_displays(self):
        return self.state_ids.stage_id.prep_display_id

    def _kitchen_history(self, move_type, **vals):
        return self.env["pos.kitchen.assignment.history"].sudo().create(dict(vals, move_type=move_type))

    def _kitchen_flagged(self):
        lines = self.filtered(lambda l: l.prep_order_id.pos_order_id.config_id.kitchen_advanced)
        if not lines:
            self._kitchen_check_flag(self.prep_order_id.pos_order_id.config_id[:1])
        return lines

    #  chef assignment
    def assign_chef(self, chef_id, actor_chef_id=False, reason=False):
        lines = self._kitchen_flagged()
        actor = self._kitchen_get_actor(actor_chef_id)
        chef = self.env["pos.kitchen.chef"].browse(int(chef_id)).exists() if chef_id else self.env["pos.kitchen.chef"]
        if chef and (not chef.active or chef.company_id not in self.env.companies):
            raise AccessError(_("This chef cannot be assigned."))
        changed, not_cooked = {}, 0
        for line in lines:
            if chef and not chef._kitchen_can_cook(line.product_id):
                not_cooked += 1  # the chef does not prepare this category: leave the item as it is
                continue
            config = line.prep_order_id.pos_order_id.config_id
            station = line.station_id or line._kitchen_displays().station_ids[:1]
            if chef and config.kitchen_strict_chef_station and chef.station_ids and station \
                    and station not in chef.station_ids:
                raise AccessError(_("Chef %(chef)s does not work on station %(station)s.",
                                    chef=chef.name, station=station.name))
            previous = line.assigned_chef_id
            if previous == chef:
                continue
            line.assigned_chef_id = chef
            line._kitchen_history(
                "reassign" if previous and chef else "assign",
                prep_line_id=line.id, pos_order_id=line.prep_order_id.pos_order_id.id,
                product_id=line.product_id.id, previous_chef_id=previous.id, new_chef_id=chef.id,
                previous_station_id=line.station_id.id, new_station_id=line.station_id.id,
                changed_by_chef_id=actor.id, reason=reason)
            changed[line.id] = chef.id or False
        if not_cooked and not changed and chef:
            raise AccessError(_("Chef %s does not prepare the category of this item.", chef.name))
        changed_lines = lines.filtered(lambda l: l.id in changed)
        changed_lines._kitchen_sync_performance()
        for display in changed_lines._kitchen_displays():
            display._notify("CHEF_ASSIGNED", {"assignments": changed})
        return True

    #  re-prepare (6.6)
    def reprepare(self, reason=False, actor_chef_id=False):
        """RPC (called with [line_ids, reason, actor_chef_id]).

        Used when the waiter changed an order: the chef starts the item again (and acknowledges the change).
        Only possible while the item is still being prepared; once ready nothing can change anymore.
        """
        lines = self._kitchen_flagged()
        actor = self._kitchen_get_actor(actor_chef_id)
        lines = lines.filtered(lambda l: l.quantity - l.cancelled > 0 and any(
            s.stage_id.stage_type in ("todo", "in_progress") for s in l.state_ids))
        if not lines:
            raise UserError(_("Only items still being prepared can be re-prepared."))
        lines.state_ids.filtered(lambda s: s.stage_id.stage_type in ("todo", "in_progress")).write({"todo": True})
        now = fields.Datetime.now()
        for line in lines:
            line.write({"reprep_count": line.reprep_count + 1, "last_change_type": "reprep",
                        "last_change_at": now, "change_pending": False})
            self.env["pos.kitchen.item.history"].sudo().create({
                "prep_order_id": line.prep_order_id.id, "prep_line_id": line.id,
                "pos_order_id": line.prep_order_id.pos_order_id.id, "product_id": line.product_id.id,
                "event_type": "reprep", "old_quantity": line.quantity - line.cancelled,
                "new_quantity": line.quantity - line.cancelled, "changed_by_chef_id": actor.id,
                "notes": reason,
            })
        lines._kitchen_sync_performance()
        for display in lines._kitchen_displays():
            for order in lines.prep_order_id.pos_order_id:
                display._send_load_orders_message(False, None, order.id)
        return True

    #  reassign work (6.7)
    def reassign(self, target_station_id, reason=False, actor_chef_id=False):
        lines = self._kitchen_flagged()
        target = self.env["pos.kitchen.station"].browse(int(target_station_id)).exists()
        if not target or not target.active:
            raise UserError(_("Unknown target station."))
        actor = self._kitchen_get_actor(actor_chef_id)
        all_orders = lines.prep_order_id.pos_order_id
        before = all_orders._kitchen_readiness_snapshot()
        t_display = target.prep_display_id
        t_first = t_display.stage_ids[:1]
        moved, skipped = self.browse(), self.browse()
        source_state_ids = defaultdict(list)
        source_displays = self.env["pos.prep.display"]
        notify_orders = self.env["pos.order"]
        source_names = []
        for line in lines:
            config = line.prep_order_id.pos_order_id.config_id
            if (target.pos_config_ids and config not in target.pos_config_ids) or target.company_id != config.company_id:
                raise UserError(_("Station %(station)s is not available on this Point of Sale.", station=target.name))
            source = line.station_id or line._kitchen_displays().station_ids[:1]
            src_states = line.state_ids.filtered(lambda s: s.stage_id.prep_display_id != t_display)
            eligible = (
                src_states
                and target._kitchen_handles(line.product_id)
                and (line.quantity - line.cancelled) > 0
                and not line.assigned_chef_id
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
            line.write({"station_id": target.id, "moved_from": source.name or False})
            line._kitchen_history(
                "station_move", prep_line_id=line.id, pos_order_id=line.prep_order_id.pos_order_id.id,
                product_id=line.product_id.id, previous_station_id=source.id, new_station_id=target.id,
                changed_by_chef_id=actor.id, reason=reason)
            moved |= line
            if source and source.name not in source_names:
                source_names.append(source.name)
            notify_orders |= line.prep_order_id.pos_order_id
        moved._kitchen_sync_performance()
        all_orders._kitchen_after_state_change(before)
        for display in source_displays:
            display._notify("STATION_REASSIGNED", {"state_ids": source_state_ids[display.id]})
            display._notify("WORKLOAD_CHANGED", {})
        if moved:
            for order in notify_orders:
                t_display._send_load_orders_message(True, _("Moved from %s", ", ".join(source_names) or "-"), order.id)
            t_display._notify("WORKLOAD_CHANGED", {})
        return {"moved": moved.ids, "skipped": skipped.ids}
