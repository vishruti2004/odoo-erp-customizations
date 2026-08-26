# -*- coding: utf-8 -*-
from odoo import models, fields, api
import base64
import face_recognition
import numpy as np
from io import BytesIO
from PIL import Image
import logging

_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    allow_without_image_capture = fields.Boolean(string="Allow Attendance Without Image & Face Recognition")
    face_encoding = fields.Binary("Face Encoding", help="Serialized face encoding for recognition")
    face_image = fields.Binary("Face Image for recognition", help="Image used for face recognition")

    @api.model
    def create(self, vals):
        """Generate face encoding when employee is created with image"""
        employee = super(HrEmployee, self).create(vals)
        if employee.face_image:
            employee._generate_face_encoding()
        return employee

    def write(self, vals):
        result = super(HrEmployee, self).write(vals)
        if 'face_image' in vals:
            for employee in self:
                if employee.face_image:
                    employee._generate_face_encoding()
                else:
                    employee.face_encoding = False
                    _logger.info(f"🧹 Face encoding cleared for {employee.name}")
        return result

    def _generate_face_encoding(self):
        """Generate face encoding from employee image"""
        for emp in self:
            if emp.face_image:
                try:
                    _logger.info(f"Generating face encoding for {emp.name}")
                    img_data = base64.b64decode(emp.face_image)
                    img = np.array(Image.open(BytesIO(img_data)))
                    encodings = face_recognition.face_encodings(img)

                    if encodings:
                        emp.face_encoding = base64.b64encode(encodings[0].tobytes())
                    else:
                        emp.face_encoding = False

                except Exception as e:
                    emp.face_encoding = False
            else:
                emp.face_encoding = False

    def generate_face_encoding_manual(self):
        generated_count = 0
        for emp in self:
            if emp.face_image:
                emp._generate_face_encoding()
                if emp.face_encoding:
                    generated_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Face encodings generated for {generated_count} employees',
                'type': 'success',
                'sticky': False,
            }
        }


