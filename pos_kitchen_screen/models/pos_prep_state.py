from odoo import api, models


class PosPrepState(models.Model):
    _inherit = "pos.prep.state"

    def _kitchen_is_ready(self):
        self.ensure_one()
        return (not self.todo) or self.stage_id.stage_type in ("ready", "done")

    def _kitchen_flagged_states(self):
        return self.filtered(lambda s: s.prep_line_id.prep_order_id.pos_order_id.config_id.kitchen_advanced)

    def _kitchen_after_change(self, orders, before):
        flagged = self._kitchen_flagged_states()
        if not flagged:
            return
        flagged.prep_line_id._kitchen_sync_performance()
        orders._kitchen_after_state_change(before)
        for display in flagged.stage_id.prep_display_id:
            if display.show_workload:
                display._notify("WORKLOAD_CHANGED", {})

    def change_state_stage(self, stages, prep_display_id):
        orders = self.prep_line_id.prep_order_id.pos_order_id
        before = orders._kitchen_readiness_snapshot()
        res = super().change_state_stage(stages, prep_display_id)
        self._kitchen_after_change(orders, before)
        return res

    def change_state_status(self, todos, prep_display_id):
        orders = self.prep_line_id.prep_order_id.pos_order_id
        before = orders._kitchen_readiness_snapshot()
        res = super().change_state_status(todos, prep_display_id)
        self._kitchen_after_change(orders, before)
        return res
