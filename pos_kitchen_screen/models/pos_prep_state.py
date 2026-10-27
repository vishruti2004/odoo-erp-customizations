from odoo import _, models

FORWARD_TYPES = ("ready", "done")
WORKING_TYPES = ("todo", "in_progress")


class PosPrepState(models.Model):
    _inherit = "pos.prep.state"

    def _kitchen_is_ready(self):
        self.ensure_one()
        return (not self.todo) or self.stage_id.stage_type in FORWARD_TYPES

    def _kitchen_flagged_states(self):
        return self.filtered(lambda state: state.prep_line_id.prep_order_id.pos_order_id.config_id.kitchen_advanced)

    def _kitchen_counts(self):
        self.ensure_one()
        line = self.prep_line_id
        return line.quantity - line.cancelled > 0 and not line.pos_order_line_id.combo_line_ids

    def _kitchen_filter_stage_move(self, stages):
        Stage = self.env["pos.prep.stage"]
        warnings, blocked = [], self.browse()
        tickets = {}
        for state in self:
            tickets.setdefault(state.prep_line_id.prep_order_id.id, self.browse())
            tickets[state.prep_line_id.prep_order_id.id] |= state
        for ticket_states in tickets.values():
            self._kitchen_auto_assign_before_ready(ticket_states, stages)
            missing_chef, completing = [], self.browse()
            for state in ticket_states._kitchen_flagged_states():
                target = Stage.browse(int(stages.get(str(state.id)) or stages.get(state.id) or 0))
                if not target or target == state.stage_id or not state._kitchen_counts():
                    continue
                if target.stage_type in FORWARD_TYPES and state.stage_id.stage_type in WORKING_TYPES \
                        and not state.prep_line_id.assigned_chef_id:
                    missing_chef.append(state.prep_line_id.product_id.display_name)
                if target.stage_type == "done":
                    completing |= state
            message = False
            if missing_chef:
                message = _("Assign a chef before marking these items ready: %s",
                            ", ".join(dict.fromkeys(missing_chef)))
            elif completing:
                orders = completing.prep_line_id.prep_order_id.pos_order_id
                others = self.search([
                    ("prep_line_id.prep_order_id.pos_order_id", "in", orders.ids), ("id", "not in", self.ids)])
                waiting = others.filtered(
                    lambda other: other._kitchen_counts() and other.stage_id.stage_type not in FORWARD_TYPES)
                if waiting:
                    names = ", ".join(dict.fromkeys(
                        "%s (%s)" % (state.prep_line_id.product_id.display_name,
                                     state.prep_line_id.station_id.name or state.stage_id.prep_display_id.name)
                        for state in waiting))
                    message = _("This order cannot be completed yet. Still in preparation: %s", names)
            if message:
                warnings.append(message)
                blocked |= ticket_states
        return self - blocked, list(dict.fromkeys(warnings))

    def _kitchen_auto_assign_before_ready(self, states, stages):
        Stage = self.env["pos.prep.stage"]
        lines = self.env["pos.prep.line"]
        for state in states._kitchen_flagged_states():
            target = Stage.browse(int(stages.get(str(state.id)) or stages.get(state.id) or 0))
            line = state.prep_line_id
            if target.stage_type in FORWARD_TYPES and state.stage_id.stage_type in WORKING_TYPES \
                    and state._kitchen_counts() and not line.assigned_chef_id:
                lines |= line
        if lines:
            lines._kitchen_auto_assign(split=False)

    def _kitchen_after_change(self, orders, before):
        flagged = self._kitchen_flagged_states()
        if not flagged:
            return
        flagged.prep_line_id._kitchen_sync_performance()
        flagged.prep_line_id._kitchen_auto_overflow()
        orders._kitchen_after_state_change(before)
        for display in flagged.stage_id.prep_display_id:
            display._notify("WORKLOAD_CHANGED", {})

    def change_state_stage(self, stages, prep_display_id):
        allowed, warnings = self._kitchen_filter_stage_move(stages)
        if warnings:
            display = self.env["pos.prep.display"].browse(prep_display_id)
            for message in warnings:
                display._notify("KITCHEN_WARNING", {"message": message})
        if not allowed:
            return
        allowed_stages = {key: value for key, value in stages.items() if int(key) in allowed.ids}
        orders = allowed.prep_line_id.prep_order_id.pos_order_id
        before = orders._kitchen_readiness_snapshot()
        res = super(PosPrepState, allowed).change_state_stage(allowed_stages, prep_display_id)
        allowed._kitchen_after_change(orders, before)
        return res

    def change_state_status(self, todos, prep_display_id):
        orders = self.prep_line_id.prep_order_id.pos_order_id
        before = orders._kitchen_readiness_snapshot()
        res = super().change_state_status(todos, prep_display_id)
        self._kitchen_after_change(orders, before)
        return res
