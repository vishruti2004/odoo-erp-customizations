# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LockerPenalty(models.Model):
    _name = "locker.penalty"
    _description = "Locker Penalty"
    _order = "id desc"

    name = fields.Char(string="Name", required=True)
    company_id = fields.Many2one("res.company", string="Company")
    active = fields.Boolean(string="Active", default=True)
    amount = fields.Monetary(string="Penalty Amount", required=True, default=0.0)
    currency_id = fields.Many2one("res.currency", string="Currency", related="company_id.currency_id", store=True, readonly=True)
    period = fields.Selection([("day", "Day"), ("month", "Month"), ("year", "Year")], string="Penalty Period", required=True, default="day")
    start_after_days = fields.Integer(string="Penalty Start After", required=True, default=0, help="Number of days after locker expiry before the penalty starts.")
    description = fields.Text(string="Description")

    @api.constrains("amount", "start_after_days")
    def _check_values(self):
        for record in self:
            if record.amount < 0:
                raise ValidationError(_("Penalty Amount cannot be negative."))
            if record.start_after_days < 0:
                raise ValidationError(_("Penalty Start After cannot be negative."))

    @api.model
    def get_active_penalty(self, company=None):
        company = company or self.env.company
        return self.search(
            [
                ("active", "=", True),
                "|",
                ("company_id", "=", False),
                ("company_id", "=", company.id),
            ],
            order="id desc",
            limit=1,
        )