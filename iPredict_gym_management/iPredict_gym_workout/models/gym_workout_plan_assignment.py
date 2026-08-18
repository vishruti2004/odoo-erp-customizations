# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymWorkoutAssignment(models.Model):
    _name = "gym.workout.assignment"
    _description = "Workout Assignment"
    _order = "start_date desc"

    company_id = fields.Many2one("res.company", string="Company", related="member_id.company_id", store=True, readonly=True, index=True)
    member_id = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade", domain="[('is_gym_member', '=', True), ('company_id', '=', company_id)]")
    plan_id = fields.Many2one("gym.workout.plan", string="Workout Plan", required=True, ondelete="cascade", domain="[('company_id', '=', company_id)]")
    trainer_id = fields.Many2one("res.partner", string="Assigned By", readonly=True, default=lambda self: self.env.user.partner_id)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    days = fields.Integer(related="plan_id.days", string="Days", store=True, readonly=True)
    state = fields.Selection([("active", "Active"), ("expiring", "Expiring Soon"), ("expired", "Expired")], string="Status", default="active", required=True)
    is_renewed = fields.Boolean(string="Renewed", default=False, copy=False)

    @api.constrains("member_id", "plan_id")
    def _check_company(self):
        for record in self:
            if not record.member_id or not record.plan_id:
                continue

            if record.member_id.company_id != record.plan_id.company_id:
                raise ValidationError(
                    _(
                        "Member and Workout Plan must belong to the same company."
                    )
                )

    @api.model
    def _cron_update_workout_assignment_status(self):
        today = fields.Date.today()

        for rec in self.search([]):
            if rec.end_date < today:
                rec.state = "expired"
            elif rec.end_date <= today + timedelta(days=3):
                rec.state = "expiring"
            else:
                rec.state = "active"

    def action_renew_workout(self):
        self.ensure_one()

        if self.state != "expired":
            return True

        today = fields.Date.today()

        self.write({"is_renewed": True})

        new_assignment = self.create(
            {
                "member_id": self.member_id.id,
                "plan_id": self.plan_id.id,
                "trainer_id": self.env.user.partner_id.id,
                "start_date": today,
                "end_date": today + timedelta(days=self.plan_id.days - 1),
                "state": "active",
                "is_renewed": False,
            }
        )

        new_assignment.member_id.message_post(
            subject=_("Workout Plan Renewed"),
            body=_(
                "Workout Plan: %s\n"
                "Renewed By: %s\n"
                "Start Date: %s\n"
                "End Date: %s"
            )
            % (
                new_assignment.plan_id.name,
                self.env.user.partner_id.name,
                new_assignment.start_date,
                new_assignment.end_date,
            ),
        )

        return True