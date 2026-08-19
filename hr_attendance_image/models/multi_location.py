# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.
from odoo import fields, models


class MultiLocation(models.Model):
    _name = "multi.location"

    name = fields.Char(help="Check-in or Check-out Area")
    face_attendance_latitude = fields.Float(
        digits=(10, 7),
        help="Company location latitude for face attendance validation"
    )
    face_attendance_longitude = fields.Float(
        digits=(10, 7),
        help="Company location longitude for face attendance validation"
    )
    face_attendance_radius = fields.Float(
        help="Radius setting for face attendance location validation."
             " If set, employees must be within this distance (in meters) "
             "from the company location to mark attendance via face recognition."
    )
    company_id = fields.Many2one('res.company', string="Company", required=True,
                                 ondelete='cascade')
