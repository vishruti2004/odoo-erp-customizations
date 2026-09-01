# -*- coding: utf-8 -*-

import base64
import secrets
import uuid
from io import BytesIO

import qrcode

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LockerAccessCredential(models.Model):
    _name = "locker.access.credential"
    _description = "Locker Access Credential"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "partner_id"
    _order = "id desc"

    _pin_code_unique = models.Constraint(
        "UNIQUE(pin_code)",
        "This PIN is already assigned to another locker credential.",
    )
    _rfid_uid_unique = models.Constraint(
        "UNIQUE(rfid_uid)",
        "This RFID UID is already assigned to another locker credential.",
    )
    _qr_token_unique = models.Constraint(
        "UNIQUE(qr_token)",
        "This QR Token is already assigned to another locker credential.",
    )

    allocation_id = fields.Many2one("locker.allocation", string="Locker Allocation", required=True, ondelete="cascade", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Person", required=True, ondelete="restrict", tracking=True)
    access_method = fields.Selection(related="allocation_id.access_method", string="Access Method", store=True, readonly=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)

    pin_code = fields.Char(string="PIN Code", copy=False, tracking=True)
    rfid_uid = fields.Char(string="RFID UID", copy=False, tracking=True)
    qr_token = fields.Char(string="QR Token", copy=False, tracking=True)
    qr_code = fields.Binary(string="QR Code", attachment=True, copy=False)
    biometric_id = fields.Char(string="Biometric ID", copy=False, tracking=True)

    @api.depends("partner_id", "allocation_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.partner_id and rec.allocation_id:
                rec.display_name = f"{rec.partner_id.display_name} - {rec.allocation_id.name}"
            elif rec.partner_id:
                rec.display_name = rec.partner_id.display_name
            else:
                rec.display_name = _("New")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            allocation_id = vals.get("allocation_id")
            partner_id = vals.get("partner_id")

            if allocation_id and partner_id:
                allocation = self.env["locker.allocation"].browse(allocation_id)
                if allocation.exists():
                    allowed_partner_ids = allocation.authorized_partner_ids.ids + [allocation.partner_id.id]
                    if partner_id not in allowed_partner_ids:
                        raise ValidationError(_("This person is not authorized for this locker allocation."))

        return super().create(vals_list)

    # CREDENTIAL ACTIONS

    def action_generate_credential(self):
        """Generates credentials based on configured access method."""
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
                rec.action_clear_credential()

    def _generate_pin(self):
        """Generates a unique 6-digit PIN code."""
        for rec in self:
            for _attempt in range(20):
                pin = str(secrets.randbelow(900000) + 100000)
                existing = rec.search_count([
                    ("id", "!=", rec.id),
                    ("active", "=", True),
                    ("pin_code", "=", pin),
                ])
                if not existing:
                    rec.write({
                        "pin_code": pin,
                        "rfid_uid": False,
                        "qr_token": False,
                        "qr_code": False,
                        "biometric_id": False,
                    })
                    if "locker_pin" in rec.partner_id._fields:
                        rec.partner_id.write({"locker_pin": pin})
                    return

            raise ValidationError(_("Unable to generate a unique PIN. Please try again."))

    def _generate_rfid(self):
        """Generates a unique 10-digit RFID UID."""
        for rec in self:
            for _attempt in range(20):
                rfid = str(secrets.randbelow(9000000000) + 1000000000)
                existing = rec.search_count([
                    ("id", "!=", rec.id),
                    ("active", "=", True),
                    ("rfid_uid", "=", rfid),
                ])
                if not existing:
                    rec.write({
                        "pin_code": False,
                        "rfid_uid": rfid,
                        "qr_token": False,
                        "qr_code": False,
                        "biometric_id": False,
                    })
                    return

            raise ValidationError(_("Unable to generate a unique RFID number. Please try again."))

    def _generate_qr(self):
        """Generates a unique QR token and QR image."""
        for rec in self:
            for _attempt in range(20):
                qr_token = str(uuid.uuid4())
                existing = rec.search_count([
                    ("id", "!=", rec.id),
                    ("active", "=", True),
                    ("qr_token", "=", qr_token),
                ])
                if existing:
                    continue

                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_token)
                qr.make(fit=True)

                buffer = BytesIO()
                qr.make_image().save(buffer, format="PNG")
                qr_code_b64 = base64.b64encode(buffer.getvalue())

                rec.write({
                    "pin_code": False,
                    "rfid_uid": False,
                    "qr_token": qr_token,
                    "qr_code": qr_code_b64,
                    "biometric_id": False,
                })
                return

            raise ValidationError(_("Unable to generate a unique QR token."))

    def action_clear_credential(self):
        self.write({
            "pin_code": False,
            "rfid_uid": False,
            "qr_token": False,
            "qr_code": False,
            "biometric_id": False,
        })

    # CONSTRAINS & VALIDATIONS

    @api.constrains("allocation_id", "partner_id")
    def _check_authorized_person(self):
        for rec in self:
            if not rec.allocation_id or not rec.partner_id:
                continue

            allowed_partner_ids = set(
                rec.allocation_id.authorized_partner_ids.ids
                + [rec.allocation_id.partner_id.id]
            )
            if rec.partner_id.id not in allowed_partner_ids:
                raise ValidationError(_("The selected person is not authorized for this locker allocation."))

    @api.constrains("pin_code")
    def _check_pin_code(self):
        for rec in self:
            if not rec.pin_code:
                continue
            if not rec.pin_code.isdigit():
                raise ValidationError(_("PIN Code must contain only numbers."))
            if len(rec.pin_code) != 6:
                raise ValidationError(_("PIN Code must contain exactly 6 digits."))