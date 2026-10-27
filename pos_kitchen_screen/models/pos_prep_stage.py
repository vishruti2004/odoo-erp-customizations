from odoo import api, fields, models


class PosPrepStage(models.Model):
    _inherit = "pos.prep.stage"

    stage_type = fields.Selection(
        [("todo", "To do"), ("in_progress", "In progress"), ("ready", "Ready"), ("done", "Done")],
        compute="_compute_stage_type", store=True, readonly=False, index=True,
        help="Computed from the position by default (first = to do, second last = ready, last = done). "
             "Native stages have no type: position is the meaning.")

    @api.depends("prep_display_id.stage_ids", "sequence")
    def _compute_stage_type(self):
        for stage in self:
            stages = stage.prep_display_id.stage_ids.sorted(lambda stage: (stage.sequence, stage.id))
            count = len(stages)
            if not count or stage not in stages:
                stage.stage_type = "todo"
                continue
            idx = list(stages.ids).index(stage.id)
            if count == 1 or idx == 0:
                stage.stage_type = "todo"
            elif idx == count - 1:
                stage.stage_type = "done"
            elif count >= 3 and idx == count - 2:
                stage.stage_type = "ready"
            else:
                stage.stage_type = "in_progress"
