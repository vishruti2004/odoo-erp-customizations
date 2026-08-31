from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    face_image = fields.Binary(
        string="Face Image",
        related='employee_id.face_image',
        readonly=False
    )

    allow_without_image_capture = fields.Boolean(
        related='employee_id.allow_without_image_capture',
        readonly=True
    )