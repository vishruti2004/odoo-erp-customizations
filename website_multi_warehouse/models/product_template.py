from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    warehouse_price_ids = fields.One2many('warehouse.product.price', compute='_compute_warehouse_price_ids', string='Warehouse Cost')

    def _compute_warehouse_price_ids(self):
        for tmpl in self:
            if tmpl.product_variant_count == 1:
                tmpl.warehouse_price_ids = self.env['warehouse.product.price'].search([('product_id', '=', tmpl.product_variant_id.id)])
            else:
                tmpl.warehouse_price_ids = self.env['warehouse.product.price'].browse()