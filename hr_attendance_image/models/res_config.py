# -*- coding: utf-8 -*-
from odoo import fields,api,models

class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_image_capture = fields.Boolean(default=False)
    face_recognition = fields.Boolean(string="Face Recognition for Check In/Out", default=False)
    face_recognition_kiosk = fields.Boolean(string="Face Recognition  Kiosk", default=False)
    face_recognition_backend = fields.Boolean(string="Face Recognition Backend", default=False)
    multi_location_ids = fields.One2many('multi.location', 'company_id', string="Multi Locations")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_image_capture = fields.Boolean(related='company_id.attendance_image_capture', readonly=False)
    face_recognition = fields.Boolean(related='company_id.face_recognition',readonly=False)
    face_recognition_kiosk = fields.Boolean(string="Face Recognition  Kiosk", related='company_id.face_recognition_kiosk', readonly=False)
    face_recognition_backend = fields.Boolean(string="Face Recognition Backend", related='company_id.face_recognition_backend', readonly=False)
    multi_location_ids = fields.One2many(related='company_id.multi_location_ids', string="Multi Locations",readonly=False)
