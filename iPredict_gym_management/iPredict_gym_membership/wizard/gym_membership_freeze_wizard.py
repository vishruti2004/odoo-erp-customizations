# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymMembershipFreezeWizard(models.TransientModel):
    _name = "gym.membership.freeze.wizard"
    _description = "Gym Membership Freeze Wizard"

    partner_id = fields.Many2one("res.partner", string="Member", required=True, readonly=True)
    membership_history_id = fields.Many2one("gym.membership.history", string="Active Membership", required=True, readonly=True)
    membership_plan_id = fields.Many2one("gym.membership.plan", string="Membership Plan", related="membership_history_id.membership_plan_id", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", related="partner_id.company_id", readonly=True)
    freeze_start_date = fields.Date(string="Start Date", required=True)
    freeze_end_date = fields.Date(string="End Date", required=True)
    freeze_days = fields.Integer(string="Freeze Days", compute="_compute_freeze_days")
    reason = fields.Text(string="Freeze Reason", required=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)

        partner_id = (
            vals.get("partner_id")
            or self.env.context.get("default_partner_id")
            or self.env.context.get("active_id")
        )

        if not partner_id:
            return vals

        partner = self.env["res.partner"].browse(partner_id).exists()
        if not partner:
            return vals

        vals["partner_id"] = partner.id

        membership_id = self.env.context.get("default_membership_history_id")
        if membership_id:
            membership = self.env["gym.membership.history"].browse(membership_id).exists()
            if (
                membership
                and membership.member_id == partner
                and membership.status == "active"
            ):
                vals["membership_history_id"] = membership.id

        if not vals.get("membership_history_id"):
            active_membership = self.env["gym.membership.history"].search(
                [
                    ("member_id", "=", partner.id),
                    ("status", "=", "active"),
                    ("company_id", "=", partner.company_id.id),
                ],
                order="membership_start_date desc, id desc",
                limit=1,
            )
            if active_membership:
                vals["membership_history_id"] = active_membership.id

        return vals

    @api.depends("freeze_start_date", "freeze_end_date")
    def _compute_freeze_days(self):
        for wizard in self:
            if (
                wizard.freeze_start_date
                and wizard.freeze_end_date
                and wizard.freeze_end_date >= wizard.freeze_start_date
            ):
                wizard.freeze_days = (wizard.freeze_end_date - wizard.freeze_start_date).days + 1
            else:
                wizard.freeze_days = 0

    @api.constrains("freeze_start_date", "freeze_end_date")
    def _check_dates(self):
        for wizard in self:
            if (
                wizard.freeze_start_date
                and wizard.freeze_end_date
                and wizard.freeze_end_date < wizard.freeze_start_date
            ):
                raise ValidationError(_("End Date must be greater than or equal to Start Date."))

    def action_submit(self):
        self.ensure_one()

        if not self.partner_id:
            raise ValidationError(_("No member is selected."))

        if not self.membership_history_id:
            raise ValidationError(_("This member does not have an active membership."))

        membership = self.membership_history_id

        if membership.member_id != self.partner_id:
            raise ValidationError(_("The selected membership does not belong to this member."))

        if membership.status != "active":
            raise ValidationError(_("Only an active membership can be frozen."))

        if self.freeze_end_date < self.freeze_start_date:
            raise ValidationError(_("End Date must be greater than or equal to Start Date."))

        if membership.membership_end_date and self.freeze_start_date > membership.membership_end_date:
            raise ValidationError(_("Freeze Start Date cannot be after the membership End Date."))

        if not self.reason or not self.reason.strip():
            raise ValidationError(_("Please enter a freeze reason."))

        existing_request = self.env["gym.membership.freeze"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("membership_history_id", "=", membership.id),
                ("state", "in", ["draft", "pending", "approved"]),
                ("freeze_start_date", "<=", self.freeze_end_date),
                ("freeze_end_date", ">=", self.freeze_start_date),
            ],
            limit=1,
        )

        if existing_request:
            raise ValidationError(_("A freeze request already exists for the selected period."))

        request = self.env["gym.membership.freeze"].create({
            "partner_id": self.partner_id.id,
            "membership_history_id": membership.id,
            "freeze_start_date": self.freeze_start_date,
            "freeze_end_date": self.freeze_end_date,
            "reason": self.reason.strip(),
            "state": "draft",
        })

        request.action_submit()

        return {"type": "ir.actions.act_window_close"}