from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    low_stock_min_qty = fields.Float(related='company_id.low_stock_min_qty', string='Global Minimum Quantity', readonly=False)
    low_stock_manager_ids = fields.Many2many(related='company_id.low_stock_manager_ids', string='Stock Managers', readonly=False)