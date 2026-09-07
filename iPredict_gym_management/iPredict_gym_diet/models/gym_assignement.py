# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymDietAssignment(models.Model):
    _name = "gym.diet.assignment"
    _description = "Diet Assignment"
    _order = "start_date desc"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="member_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    member_id = fields.Many2one(
        "res.partner",
        string="Member",
        required=True,
        ondelete="cascade",
        domain="[('is_gym_member', '=', True), ('company_id', '=', company_id)]",
    )
    plan_id = fields.Many2one(
        "gym.diet.plan",
        string="Diet Plan",
        required=True,
        ondelete="cascade",
        domain="[('company_id', '=', company_id)]",
    )
    trainer_id = fields.Many2one(
        "res.partner",
        string="Trainer",
        readonly=True,
        default=lambda self: self.env.user.partner_id,
    )
    start_date = fields.Date(
        string="Start Date",
        required=True,
    )
    end_date = fields.Date(
        string="End Date",
        required=True,
    )
    state = fields.Selection(
        [
            ("upcoming", "Upcoming"),
            ("active", "Running"),
            ("expired", "Expired"),
        ],
        string="Status",
        default="upcoming",
        required=True,
    )
    is_renewed = fields.Boolean(
        string="Renewed",
        default=False,
        copy=False,
    )

    @api.constrains("member_id", "plan_id")
    def _check_company(self):
        for record in self:
            if not record.member_id or not record.plan_id:
                continue

            if (
                record.member_id.company_id
                and record.plan_id.company_id
                and record.member_id.company_id != record.plan_id.company_id
            ):
                raise ValidationError(
                    _("The Member and Diet Plan must belong to the same company.")
                )

    @api.model
    def _cron_update_diet_assignment_status(self):
        today = fields.Date.today()

        for rec in self.search([]):
            if rec.start_date > today:
                rec.state = "upcoming"
            elif rec.end_date < today:
                rec.state = "expired"
            else:
                rec.state = "active"

    def action_renew_diet(self):
        self.ensure_one()

        if self.state != "expired":
            return True

        today = fields.Date.today()

        self.write({
            "is_renewed": True,
        })

        new_assignment = self.create({
            "member_id": self.member_id.id,
            "plan_id": self.plan_id.id,
            "trainer_id": self.env.user.partner_id.id,
            "start_date": today,
            "end_date": today + timedelta(days=self.plan_id.days - 1),
            "state": "active",
            "is_renewed": False,
        })

        new_assignment.member_id.message_post(
            subject=_("Diet Plan Renewed"),
            body=_(
                "Diet Plan: %s\n"
                "Company: %s\n"
                "Renewed By: %s\n"
                "Start Date: %s\n"
                "End Date: %s"
            ) % (
                new_assignment.plan_id.name,
                new_assignment.company_id.name,
                self.env.user.partner_id.name,
                new_assignment.start_date,
                new_assignment.end_date,
            ),
        )

        return True
