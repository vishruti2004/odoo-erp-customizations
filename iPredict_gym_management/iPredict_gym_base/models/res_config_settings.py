# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gym_create_employee_for_member = fields.Boolean(
        string="Create Employee for Gym Members",
        related="company_id.gym_create_employee_for_member",
        readonly=False,
    )

    gym_member_attendance = fields.Boolean(
        string="Enable Member Attendance Management",
        related="company_id.gym_member_attendance",
        readonly=False,
    )

    gym_member_attendance_qr = fields.Boolean(
        string="Manage Member Attendance via QR Code",
        related="company_id.gym_member_attendance_qr",
        readonly=False,
    )

    gym_attendance_qr_code = fields.Binary(
        related="company_id.gym_attendance_qr_code",
        readonly=True,
    )

    def action_generate_attendance_qr(self):
        self.ensure_one()
        self.company_id.action_generate_attendance_qr()
        return True