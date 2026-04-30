from odoo import fields, models

class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    allow_discount = fields.Boolean(
        string='Allow Discount',
        default=False,
    )
    
    discount_percentage = fields.Float(
        string='Discount Percentage',
        digits=(16, 2),
    )