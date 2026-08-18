# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymWorkoutPlanAssignWizard(models.TransientModel):
    _name = "gym.workout.plan.assign.wizard"
    _description = "Assign Members Wizard"

    plan_id = fields.Many2one("gym.workout.plan", string="Workout Plan", required=True, domain="[('company_id', '=', company_id)]")
    company_id = fields.Many2one("res.company", string="Company", related="plan_id.company_id", store=True, readonly=True)
    member_ids = fields.Many2many("res.partner", string="Assign To", domain="[('is_gym_member', '=', True), ('company_id', '=', company_id)]")
    start_date = fields.Date(string="Date From", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Date To")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user

        if user.has_group("iPredict_gym_base.group_gym_user") and not user.has_group("iPredict_gym_base.group_gym_admin"):
            trainer = user.employee_id
            if trainer:
                member_ids = trainer.member_ids.filtered(
                    lambda member: member.is_gym_member and member.company_id == trainer.company_id
                ).ids
                res["member_ids"] = [(6, 0, member_ids)]

        return res

    @api.onchange("plan_id", "start_date")
    def _onchange_dates(self):
        if self.plan_id and self.start_date:
            self.end_date = self.start_date + timedelta(days=self.plan_id.days - 1)
        else:
            self.end_date = False

    def action_assign(self):
        self.ensure_one()

        if not self.plan_id:
            raise ValidationError(_("Please select a Workout Plan."))

        if not self.member_ids:
            raise ValidationError(_("Please select at least one member."))

        if not self.start_date:
            raise ValidationError(_("Please select a start date."))

        if not self.end_date:
            raise ValidationError(_("Please select an end date."))

        if self.start_date < fields.Date.today():
            raise ValidationError(_("Past dates are not allowed."))

        plan_company = self.plan_id.company_id

        if not plan_company:
            raise ValidationError(_("The selected Workout Plan has no company configured."))

        for member in self.member_ids:
            if member.company_id != plan_company:
                raise ValidationError(
                    _(
                        "Member '%(member)s' belongs to '%(member_company)s', "
                        "but the Workout Plan '%(plan)s' belongs to '%(plan_company)s'.\n\n"
                        "Member and Workout Plan must belong to the same company."
                    )
                    % {
                        "member": member.name,
                        "member_company": member.company_id.name,
                        "plan": self.plan_id.name,
                        "plan_company": plan_company.name,
                    }
                )

            if not member.is_gym_member:
                raise ValidationError(_("Member '%s' is not marked as a Gym Member.") % member.name)

        assignment_obj = self.env["gym.workout.assignment"]

        for member in self.member_ids:
            existing_assignment = assignment_obj.search(
                [
                    ("member_id", "=", member.id),
                    ("plan_id", "=", self.plan_id.id),
                    ("company_id", "=", plan_company.id),
                    ("start_date", "<=", self.end_date),
                    ("end_date", ">=", self.start_date),
                ],
                limit=1,
            )

            if existing_assignment:
                raise ValidationError(
                    _("Workout plan '%(plan)s' is already assigned to %(member)s during the selected period.")
                    % {
                        "plan": self.plan_id.name,
                        "member": member.name,
                    }
                )

            assignment_obj.create(
                {
                    "member_id": member.id,
                    "plan_id": self.plan_id.id,
                    "trainer_id": self.env.user.partner_id.id,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                }
            )

        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        return {"type": "ir.actions.act_window_close"}