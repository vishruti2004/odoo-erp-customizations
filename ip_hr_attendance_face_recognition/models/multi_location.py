# Part of Odoo. See COPYRIGHT & LICENSE files for full copyright and licensing details.
from odoo import fields, models


class MultiLocation(models.Model):
    _name = "multi.location"
    _description = "Multi Location"

    name = fields.Char(string="Location Name", help="Check-in or Check-out Area")
    face_attendance_latitude = fields.Float(string="Latitude", digits=(10, 7), help="Company location latitude for face attendance validation")
    face_attendance_longitude = fields.Float(string="Longitude", digits=(10, 7), help="Company location longitude for face attendance validation")
    face_attendance_radius = fields.Float(string="Radius (meters)", help="Radius setting for face attendance location validation. If set, employees must be within this distance (in meters) from the company location to mark attendance via face recognition.")
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, ondelete="cascade")