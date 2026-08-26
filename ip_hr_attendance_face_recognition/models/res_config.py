# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    attendance_image_capture = fields.Boolean(string="Attendance Image Capture", default=False)
    face_recognition = fields.Boolean(string="Face Recognition for Check In/Out", default=False)
    face_recognition_kiosk = fields.Boolean(string="Face Recognition Kiosk", default=False)
    face_recognition_backend = fields.Boolean(string="Face Recognition Backend", default=False)
    multi_location_ids = fields.Many2many("multi.location", "res_company_multi_location_rel", "company_id", "location_id", string="Multi Locations")


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    attendance_image_capture = fields.Boolean(related="company_id.attendance_image_capture", readonly=False)
    face_recognition = fields.Boolean(related="company_id.face_recognition", readonly=False)
    face_recognition_kiosk = fields.Boolean(string="Face Recognition Kiosk", related="company_id.face_recognition_kiosk", readonly=False)
    face_recognition_backend = fields.Boolean(string="Face Recognition Backend", related="company_id.face_recognition_backend", readonly=False)
    multi_location_ids = fields.Many2many(related="company_id.multi_location_ids", string="Multi Locations", readonly=False)