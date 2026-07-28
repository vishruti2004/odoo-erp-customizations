from datetime import timedelta
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymDietPlanAssignWizard(models.TransientModel):
    _name = "gym.diet.plan.assign.wizard"
    _description = "Assign Diet Plan Wizard"

    plan_id = fields.Many2one("gym.diet.plan", string="Diet Plan", required=True)
    member_ids = fields.Many2many("res.partner", string="Assign To", domain="[('is_gym_member', '=', True)]")
    start_date = fields.Date(string="Date From", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Date To")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        user = self.env.user
        if (
            user.has_group("iPredict_gym_base.group_gym_trainer")
            and not user.has_group("iPredict_gym_base.group_gym_admin")
        ):
            trainer = user.employee_id
            if trainer:
                res["member_ids"] = [(6, 0, trainer.member_ids.ids)]

        return res

    @api.onchange("plan_id", "start_date")
    def _onchange_dates(self):
        if self.plan_id and self.start_date:
            self.end_date = self.start_date + timedelta(
                days=self.plan_id.days - 1
            )
        else:
            self.end_date = False

    def action_assign(self):
        self.ensure_one()

        if not self.member_ids:
            raise ValidationError(_("Please select at least one member."))

        if not self.start_date:
            raise ValidationError(_("Please select a start date."))

        # Past date validation
        if self.start_date < fields.Date.today():
            raise ValidationError(
                _("Past dates are not allowed.")
            )

        assignment_obj = self.env["gym.diet.assignment"]

        for member in self.member_ids:

            # Same member + same plan + overlapping dates
            existing_assignment = assignment_obj.search([
                ("member_id", "=", member.id),
                ("plan_id", "=", self.plan_id.id),
                ("start_date", "<=", self.end_date),
                ("end_date", ">=", self.start_date),
            ], limit=1)

            if existing_assignment:
                raise ValidationError(_(
                    "Workout plan '%(plan)s' is already assigned to %(member)s during the selected period."
                ) % {
                    "plan": self.plan_id.name,
                    "member": member.name,
                })

            assignment_obj.create({
                "member_id": member.id,
                "plan_id": self.plan_id.id,
                "trainer_id": self.env.user.partner_id.id,
                "start_date": self.start_date,
                "end_date": self.end_date,
            })

        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}