from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class GymWorkoutPlanAssignWizard(models.TransientModel):
    _name = "gym.workout.plan.assign.wizard"
    _description = "Assign Members Wizard"

    plan_id = fields.Many2one("gym.workout.plan", string="Workout Plan", required=True)
    member_ids = fields.Many2many("res.partner", string="Assign To", domain="[('is_gym_member', '=', True)]")
    start_date = fields.Date(string="Date From", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Date To")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user
        if user.has_group("iPredict_gym_base.group_gym_trainer") and not user.has_group("iPredict_gym_base.group_gym_admin"):
            trainer = user.employee_id
            if trainer:
                res["member_ids"] = [(6, 0, trainer.member_ids.ids)]
        return res

    def action_assign(self):
        self.ensure_one()

        if not self.member_ids:
            raise ValidationError(_("Please select at least one member."))

        Assignment = self.env["gym.workout.assignment"]

        for member in self.member_ids:
            Assignment.create({
                "member_id": member.id,
                "plan_id": self.plan_id.id,
                "start_date": self.start_date,
                "end_date": self.end_date,
            })

        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}