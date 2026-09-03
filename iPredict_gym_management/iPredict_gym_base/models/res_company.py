# -*- coding: utf-8 -*-

import base64
import uuid
from io import BytesIO

import qrcode

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    gym_create_employee_for_member = fields.Boolean(
        string="Create Employee for Gym Members",
        default=False,
        help="Allow gym members to create an employee from the member form.",
    )

    gym_member_attendance = fields.Boolean(
        string="Enable Member Attendance Management",
        default=False,
        help="Enable attendance management for gym members.",
    )

    gym_member_attendance_qr = fields.Boolean(
        string="Manage Member Attendance via QR Code",
        default=False,
        help="Allow gym members to manage attendance using QR code.",
    )

    gym_attendance_qr_token = fields.Char(
        string="Attendance QR Token",
        copy=False,
    )

    gym_attendance_qr_code = fields.Binary(
        string="Attendance QR Code",
        attachment=True,
        copy=False,
    )

    def action_generate_attendance_qr(self):
        """Generate a unique QR token and QR image."""
        for company in self:
            qr_token = str(uuid.uuid4())

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

            company.write({
                "gym_attendance_qr_token": qr_token,
                "gym_attendance_qr_code": qr_code_b64,
            })

        return True