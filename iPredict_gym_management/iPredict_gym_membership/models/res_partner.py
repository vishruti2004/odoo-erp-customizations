# -*- coding: utf-8 -*-

from datetime import timedelta
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    membership_plan_id = fields.Many2one("gym.membership.plan", string="Membership Plan", tracking=True)
    work_schedule_id = fields.Many2one("resource.calendar", string="Work Schedule", tracking=True)
    auto_renew = fields.Boolean(string="Auto Renew", tracking=True)
    is_frozen = fields.Boolean(string="Membership Frozen", tracking=True)
    freeze_start_date = fields.Date(string="Freeze Start", tracking=True)
    freeze_end_date = fields.Date(string="Freeze End", tracking=True)
    freeze_days = fields.Integer(string="Freeze Days", compute="_compute_freeze_days", store=True)
    remaining_days = fields.Integer(string="Remaining Days", compute="_compute_remaining_days", store=True)
    notes = fields.Text(string="Notes")
    membership_start_date = fields.Date(string="Start Date", tracking=True)
    membership_end_date = fields.Date(string="End Date", compute="_compute_membership_end_date", store=True, tracking=True)
    is_gym_member = fields.Boolean(string="Gym Member", default=False, tracking=True)
    membership_history_ids = fields.One2many("gym.membership.history", "member_id", string="Membership History")
    member_code = fields.Char(string="Member ID", readonly=True, copy=False, index=True)
    trainer_id = fields.Many2many("hr.employee", string="Trainer", domain=[("is_trainer", "=", True)])

    @api.depends("freeze_start_date", "freeze_end_date")
    def _compute_freeze_days(self):
        for record in self:
            record.freeze_days = 0
            if record.freeze_start_date and record.freeze_end_date:
                record.freeze_days = (record.freeze_end_date - record.freeze_start_date).days + 1

    @api.depends("membership_start_date", "membership_plan_id.duration", "membership_plan_id.duration_uom")
    def _compute_membership_end_date(self):
        for record in self:
            record.membership_end_date = False

            if not record.membership_start_date or not record.membership_plan_id:
                continue

            duration = record.membership_plan_id.duration
            unit = record.membership_plan_id.duration_uom

            if unit == "days":
                record.membership_end_date = record.membership_start_date + timedelta(days=duration)
            elif unit == "months":
                record.membership_end_date = fields.Date.add(record.membership_start_date, months=duration)
            elif unit == "years":
                record.membership_end_date = fields.Date.add(record.membership_start_date, years=duration)

    @api.depends("membership_end_date")
    def _compute_remaining_days(self):
        today = fields.Date.today()
        for record in self:
            record.remaining_days = 0
            if record.membership_end_date:
                remaining = (record.membership_end_date - today).days
                record.remaining_days = max(remaining, 0)

    # ACTION METHODS

    def action_freeze_membership(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Membership Freeze Requests",
            "res_model": "gym.membership.freeze",
            "view_mode": "list,form",
            "domain": [("partner_id", "=", self.id)],
            "context": {
                "default_partner_id": self.id,
                "default_freeze_start_date": self.freeze_start_date,
                "default_freeze_end_date": self.freeze_end_date,
            },
            "target": "current",
        }