# -*- coding: utf-8 -*-

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Locker Settings
    available_locker_color = fields.Char(string="Available Locker Color", related="company_id.available_locker_color", readonly=False)
    allocated_locker_color = fields.Char(string="Allocated Locker Color", related="company_id.allocated_locker_color", readonly=False)
    renewal_reminder_days = fields.Integer(string="Renewal Reminder Days", related="company_id.renewal_reminder_days", readonly=False)
