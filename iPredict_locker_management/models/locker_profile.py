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
    is_rental = fields.Boolean(string="Is Rental", tracking=True, help="Enable this option if lockers of this profile are rented.")
    rental_product_id = fields.Many2one("product.product", string="Rental Product", domain="[('type', '=', 'service')]", tracking=True)
    deposit_required = fields.Boolean(string="Deposit Required", tracking=True)
    deposit_product_id = fields.Many2one("product.product", string="Deposit Product", domain="[('type', '=', 'service')]", tracking=True)
    access_method = fields.Selection([("physical_key", "Physical Key"), ("pin", "PIN Code"), ("qr", "QR Code"), ("rfid", "RFID Card"), ("biometric", "Biometric")], string="Access Method", default="physical_key", required=True, tracking=True)
    locker_ids = fields.One2many("locker.locker", "profile_id", string="Lockers")
    locker_count = fields.Integer(string="Locker Count", compute="_compute_locker_count")


    @api.depends("locker_ids")
    def _compute_locker_count(self):
        for rec in self:
            rec.locker_count = len(rec.locker_ids)

    @api.constrains("is_rental", "rental_product_id", "deposit_required", "deposit_product_id")
    def _check_rental_configuration(self):
        for rec in self:
            if rec.is_rental and not rec.rental_product_id:
                raise ValidationError("Please select a Rental Product.")

            if rec.is_rental and rec.deposit_required and not rec.deposit_product_id:
                raise ValidationError("Please select a Deposit Product.")

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