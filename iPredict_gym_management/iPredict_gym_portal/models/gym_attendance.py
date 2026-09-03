# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GymAttendance(models.Model):
    _name = "gym.attendance"
    _description = "Gym Attendance"
    _order = "check_in desc, id desc"

    member_id = fields.Many2one(
        "res.partner",
        string="Member",
        required=True,
        index=True,
        ondelete="cascade",
    )

    membership_id = fields.Many2one(
        "gym.membership.history",
        string="Membership",
        required=True,
        index=True,
        ondelete="restrict",
    )

    check_in = fields.Datetime(
        string="Check In",
        required=True,
        default=fields.Datetime.now,
        index=True,
    )

    check_out = fields.Datetime(
        string="Check Out",
        index=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    status = fields.Selection(
        [
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
        ],
        string="Status",
        required=True,
        default="checked_in",
    )

    @api.constrains("check_in", "check_out")
    def _check_checkout(self):
        for record in self:
            if record.check_out and record.check_out < record.check_in:
                raise ValidationError(
                    "Check Out cannot be earlier than Check In."
                )