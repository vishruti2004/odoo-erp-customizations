# -*- coding: utf-8 -*-

import secrets
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class LockerAccessCredential(models.Model):
    _name = "locker.access.credential"
    _description = "Locker Access Credential"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "partner_id"
    _order = "id desc"

    allocation_id = fields.Many2one("locker.allocation", string="Locker Allocation", required=True, ondelete="cascade", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Person", required=True, ondelete="restrict", tracking=True)
    access_method = fields.Selection(related="allocation_id.access_method", string="Access Method", store=True, readonly=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    pin_code = fields.Char(string="PIN Code", copy=False, tracking=True)
    rfid_uid = fields.Char(string="RFID UID", copy=False, tracking=True)
    qr_token = fields.Char(string="QR Token", copy=False, tracking=True)
    biometric_id = fields.Char(string="Biometric ID", copy=False, tracking=True)

    # Compute display name
    @api.depends("partner_id", "allocation_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_id and rec.allocation_id:
                rec.display_name = f"{rec.partner_id.display_name} - {rec.allocation_id.name}"
            elif rec.partner_id:
                rec.display_name = rec.partner_id.display_name
            else:
                rec.display_name = "New"

    # Create record validation
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            allocation_id, partner_id = vals.get("allocation_id"), vals.get("partner_id")
            if allocation_id and partner_id:
                allocation = self.env["locker.allocation"].browse(allocation_id)
                if allocation.exists():
                    allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]
                    if partner_id not in allowed_partner_ids:
                        raise ValidationError(_("This person is not authorized for this locker allocation."))
        return super().create(vals_list)

    # Generate credential based on access method
    def action_generate_credential(self):
        for rec in self:
            if not rec.allocation_id:
                raise ValidationError(_("Locker Allocation is required."))
            if not rec.partner_id:
                raise ValidationError(_("Person is required."))

            access_method = rec.allocation_id.access_method
            if not access_method:
                raise ValidationError(_("Please configure Access Method on Locker Profile."))

            if access_method == "pin":
                rec._generate_pin()
            elif access_method == "rfid":
                rec._generate_rfid()
            elif access_method == "qr":
                rec._generate_qr()
            elif access_method == "biometric":
                raise ValidationError(_("Biometric ID must be entered from the biometric device."))
            elif access_method == "physical_key":
                raise ValidationError(_("Physical Key does not require a digital credential."))

    # Generate unique 6 digit PIN
    def _generate_pin(self):
        self.ensure_one()
        Credential = self.env["locker.access.credential"]
        for attempt in range(20):
            pin = str(secrets.randbelow(900000) + 100000)
            existing = Credential.search([("id", "!=", self.id), ("active", "=", True), ("pin_code", "=", pin)], limit=1)
            if not existing:
                self.write({"pin_code": pin})
                if self.partner_id:
                    self.partner_id.write({"locker_pin": pin})
                return
        raise ValidationError(_("Unable to generate a unique PIN. Please try again."))

    # Generate unique RFID UID
    def _generate_rfid(self):
        self.ensure_one()
        Credential = self.env["locker.access.credential"]
        for attempt in range(20):
            rfid = str(secrets.randbelow(9000000000) + 1000000000)
            existing = Credential.search([("id", "!=", self.id), ("active", "=", True), ("rfid_uid", "=", rfid)], limit=1)
            if not existing:
                self.write({"rfid_uid": rfid})
                return
        raise ValidationError(_("Unable to generate a unique RFID number. Please try again."))

    # Generate unique QR Token
    def _generate_qr(self):
        self.ensure_one()
        Credential = self.env["locker.access.credential"]
        for attempt in range(20):
            qr_token = str(uuid.uuid4())
            existing = Credential.search([("id", "!=", self.id), ("active", "=", True), ("qr_token", "=", qr_token)], limit=1)
            if not existing:
                self.write({"qr_token": qr_token})
                return
        raise ValidationError(_("Unable to generate a unique QR token. Please try again."))

    # Clear all stored credentials
    def action_clear_credential(self):
        for rec in self:
            rec.write({"pin_code": False, "rfid_uid": False, "qr_token": False, "biometric_id": False})

    # Validate authorized person
    @api.constrains("allocation_id", "partner_id")
    def _check_authorized_person(self):
        for rec in self:
            if not rec.allocation_id or not rec.partner_id:
                continue
            allowed_partner_ids = rec.allocation_id.authorized_partner_ids.ids + [rec.allocation_id.partner_id.id]
            if rec.partner_id.id not in allowed_partner_ids:
                raise ValidationError(_("The selected person is not authorized for this locker allocation."))

    # Validate PIN format and uniqueness
    @api.constrains("pin_code")
    def _check_pin_code(self):
        for rec in self:
            if not rec.pin_code:
                continue
            if not rec.pin_code.isdigit():
                raise ValidationError(_("PIN Code must contain only numbers."))
            if len(rec.pin_code) != 6:
                raise ValidationError(_("PIN Code must contain exactly 6 digits."))
            duplicate = self.search([("id", "!=", rec.id), ("active", "=", True), ("pin_code", "=", rec.pin_code)], limit=1)
            if duplicate:
                raise ValidationError(_("This PIN is already assigned to another active locker credential."))

    # Validate RFID UID uniqueness
    @api.constrains("rfid_uid")
    def _check_rfid_uid(self):
        for rec in self:
            if not rec.rfid_uid:
                continue
            duplicate = self.search([("id", "!=", rec.id), ("active", "=", True), ("rfid_uid", "=", rec.rfid_uid)], limit=1)
            if duplicate:
                raise ValidationError(_("This RFID UID is already assigned to another active locker credential."))

    # Validate QR Token uniqueness
    @api.constrains("qr_token")
    def _check_qr_token(self):
        for rec in self:
            if not rec.qr_token:
                continue
            duplicate = self.search([("id", "!=", rec.id), ("active", "=", True), ("qr_token", "=", rec.qr_token)], limit=1)
            if duplicate:
                raise ValidationError(_("This QR Token is already assigned to another active locker credential."))