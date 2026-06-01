from odoo import fields, models
from odoo.fields import Domain

class Website(models.Model):
    _inherit = 'website'

    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Warehouse'
    )
    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist')


    def sale_product_domain(self):
        domain = super().sale_product_domain()

        if not self.warehouse_id:
            return domain

        available_ids = self.env['stock.quant'].sudo().search([
            ('location_id', 'child_of', self.warehouse_id.lot_stock_id.id),
            ('location_id.usage', '=', 'internal'),
        ]).filtered(
            lambda q: (q.quantity - q.reserved_quantity) > 0
        ).mapped('product_id.product_tmpl_id').ids

        stock_domain = Domain('id', 'in', available_ids or [0])

        return Domain.AND([domain, stock_domain])


    def _get_and_cache_current_pricelist(self):
        if self.pricelist_id:
            return self.pricelist_id
        return super()._get_and_cache_current_pricelist()
    