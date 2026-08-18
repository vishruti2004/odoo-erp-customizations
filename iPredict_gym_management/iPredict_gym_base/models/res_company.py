# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    gym_create_employee_for_member = fields.Boolean(
        string="Create Employee for Gym Members",
        default=False,
        help="Allow gym members to create an employee from the member form.",
    )