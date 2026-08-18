# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    gym_create_employee_for_member = fields.Boolean(string="Create Employee for Gym Members", related="company_id.gym_create_employee_for_member", readonly=False)