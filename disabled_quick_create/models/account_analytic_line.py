from odoo import api, fields, models

class AccountAnalyticLine(models.Model):
    _inherit = 'project.task'
 
    partner_ids = fields.Many2many('res.partner',string='Partners')