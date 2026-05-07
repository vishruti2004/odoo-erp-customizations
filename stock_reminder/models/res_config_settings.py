from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Minimum stock quantity 
    stock_alert_min_qty = fields.Integer(
        string="Minimum Stock Quantity",
        config_parameter='stock_alert.min_qty',
        default=0,
    )