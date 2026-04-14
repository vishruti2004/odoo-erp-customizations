from odoo import models, fields

class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    delivery_type = fields.Selection([
        ('days', 'Days'),
        ('hours', 'Hours')
    ], string="Delivery Type", default='days')
    
    estimated_delivery_date = fields.Integer(
        string="Duration", 
        default=1
    )