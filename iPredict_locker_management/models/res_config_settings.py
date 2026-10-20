# -*- coding: utf-8 -*-

from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Locker Settings
    available_locker_color = fields.Char(string="Available Locker Color", related="company_id.available_locker_color", readonly=False)
    allocated_locker_color = fields.Char(string="Allocated Locker Color", related="company_id.allocated_locker_color", readonly=False)
    reserved_locker_color = fields.Char(string="Reserved Locker Color", related="company_id.reserved_locker_color", readonly=False)
    locker_reservation_hours = fields.Integer(string="Locker Reservation Hours", related="company_id.locker_reservation_hours", readonly=False)
    renewal_reminder_days = fields.Integer(string="Renewal Reminder Days", related="company_id.renewal_reminder_days", readonly=False)
    locker_auth_lock_seconds = fields.Integer(string="Authentication Lock Time (seconds)", related="company_id.locker_auth_lock_seconds", readonly=False)
    enable_3d_locker_view = fields.Boolean(
        string="Enable 3D Locker View",
        related="company_id.enable_3d_locker_view",
        readonly=False,
    )