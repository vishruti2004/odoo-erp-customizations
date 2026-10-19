# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    available_locker_color = fields.Char(string="Available Locker Color", default="#28A745", help="Color for available lockers (Body Color)")
    allocated_locker_color = fields.Char(string="Allocated Locker Color", default="#DC3545", help="Color for allocated lockers (Body Color)")
    reserved_locker_color = fields.Char(string="Reserved Locker Color", default="#FFC107", help="Color for reserved lockers (Body Color)")
    locker_reservation_hours = fields.Integer(
        string="Locker Reservation Hours",
        default=24,
        help="A reserved locker (draft allocation) is released automatically after this many hours.",
    )
    renewal_reminder_days = fields.Integer(
    string="Renewal Reminder Days",
    default=5,
    help="Number of days before locker expiry when renewal becomes available."
)
    enable_3d_locker_view = fields.Boolean(
        string="Enable 3D Locker View",
        default=False,
    )
    