# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError

class LockerProfile(models.Model):
    _name = "locker.profile"
    _description = "Locker Profile"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    name = fields.Char(string="Profile Name", required=True, tracking=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Html(string="Notes")
    allocation_type = fields.Selection([("free", "Free"), ("paid", "Paid")], string="Allocation Type", default="paid", required=True, tracking=True)
    rental_product_id = fields.Many2one("product.product", string="Rental Product", domain="[('type', '=', 'service')]", tracking=True)
    deposit_required = fields.Boolean(string="Deposit Required", tracking=True)
    deposit_amount = fields.Monetary(string="Deposit Amount", currency_field="currency_id", tracking=True, help="Security deposit amount for lockers under this profile.")
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id", string="Currency", store=True, readonly=True)
    access_method = fields.Selection([("physical_key", "Physical Key"), ("pin", "PIN Code"), ("qr", "QR Code"), ("rfid", "RFID Card"), ("biometric", "Biometric")], string="Access Method", default="physical_key", required=True, tracking=True)
    locker_ids = fields.One2many("locker.locker", "profile_id", string="Lockers")
    locker_count = fields.Integer(string="Locker Count", compute="_compute_locker_count")

    @api.depends("locker_ids")
    def _compute_locker_count(self):
        for rec in self:
            rec.locker_count = len(rec.locker_ids)

    @api.constrains("rental_product_id", "deposit_required", "deposit_amount")
    def _check_rental_configuration(self):
        for rec in self:
            if not rec.rental_product_id:
                raise ValidationError("Please select a Rental Product.")

    @api.constrains("deposit_required", "deposit_amount")
    def _check_deposit_amount(self):
        for rec in self:
            if rec.deposit_required and rec.deposit_amount <= 0:
                raise ValidationError(
                    "Please enter a Deposit Amount greater than zero."
                )
    # Actions

    def action_view_lockers(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Lockers",
            "res_model": "locker.locker",
            "view_mode": "list,form",
            "domain": [("profile_id", "=", self.id)],
            "context": {
                "default_profile_id": self.id,
            },
        }