from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    low_stock_min_qty = fields.Float(string='Global Minimum Quantity')
    low_stock_manager_ids = fields.Many2many('res.users', string='Stock Managers')