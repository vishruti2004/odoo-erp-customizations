# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    available_locker_color = fields.Char(string="Available Locker Color", default="#28A745", help="Color for available lockers (Body Color)")
    allocated_locker_color = fields.Char(string="Allocated Locker Color", default="#DC3545", help="Color for allocated lockers (Body Color)")
    renewal_reminder_days = fields.Integer(
    string="Renewal Reminder Days",
    default=5,
    help="Number of days before locker expiry when renewal becomes available."
)

   