from odoo import fields, models

class ProductProduct(models.Model):
    _inherit = 'product.product'

    warehouse_price_ids = fields.One2many('warehouse.product.price', 'product_id', string='Warehouse Cost')


