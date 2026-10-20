# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LockerPenalty(models.Model):
    _name = "locker.penalty"
    _description = "Locker Penalty"
    _order = "id desc"

    name = fields.Char(string="Name", required=True)
    company_id = fields.Many2one("res.company", string="Company")
    active = fields.Boolean(string="Active", default=True)
    amount = fields.Monetary(string="Penalty Amount", required=True, default=0.0, help="Amount charged on every penalty invoice (one invoice duration).")
    currency_id = fields.Many2one("res.currency", string="Currency", related="company_id.currency_id", store=True, readonly=True)
    period = fields.Selection( [("day", "Day(s)"), ("week", "Week(s)"), ("month", "Month(s)"), ("year", "Year(s)")], string="Penalty Period", required=True, default="day")
    start_after_days = fields.Integer(string="Penalty Start After", required=True, default=0, help="How long after locker expiry the penalty starts. The unit (day / week / month / year) is the Penalty Period next to it.")
    invoice_interval = fields.Integer(
        string="Invoice Duration",
        required=True,
        default=1,
        help="How often a new penalty invoice is generated once the penalty has started. The Penalty Amount is charged for every invoice duration.",
    )
    invoice_interval_unit = fields.Selection(
        [("day", "Day(s)"), ("week", "Week(s)"), ("month", "Month(s)"), ("year", "Year(s)")],
        string="Invoice Interval Unit",
        required=True,
        default="day",
    )
    max_unpaid_invoices = fields.Integer(
        string="Max Unpaid Penalty Invoices",
        required=True,
        default=3,
        help="If this many penalty invoices are still unpaid, the locker is released "
             "automatically (becomes available) when the next penalty invoice is due. "
             "Set 0 to disable the automatic release.",
    )
    description = fields.Text(string="Description")

    @api.constrains("amount", "start_after_days", "invoice_interval", "max_unpaid_invoices")
    def _check_values(self):
        for record in self:
            if record.amount < 0:
                raise ValidationError(_("Penalty Amount cannot be negative."))
            if record.start_after_days < 0:
                raise ValidationError(_("Penalty Start After cannot be negative."))
            if record.invoice_interval < 1:
                raise ValidationError(_("Invoice Every must be at least 1."))
            if record.max_unpaid_invoices < 0:
                raise ValidationError(_("Max Unpaid Penalty Invoices cannot be negative."))

    def _get_start_delta(self):
        """relativedelta between the locker expiry and the penalty start."""
        self.ensure_one()
        unit = {"day": "days", "week": "weeks", "month": "months", "year": "years"}.get(self.period, "days")
        return relativedelta(**{unit: max(self.start_after_days or 0, 0)})

    def _get_invoice_interval_delta(self):
        """relativedelta of one penalty invoice cycle."""
        self.ensure_one()
        number = max(self.invoice_interval or 1, 1)
        unit = {"day": "days", "week": "weeks", "month": "months", "year": "years"}.get(
            self.invoice_interval_unit, "days"
        )
        return relativedelta(**{unit: number})

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