from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_patient = fields.Boolean(string="Is Patient")
    is_doctor = fields.Boolean(string="Is Doctor")
