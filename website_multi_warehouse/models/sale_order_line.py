from odoo import models, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id', 'company_id', 'currency_id', 'product_uom_id', 'product_uom_qty', 'order_id.warehouse_id')
    def _compute_purchase_price(self):
        for line in self:
            if not line.product_id:
                line.purchase_price = 0.0
                continue

            warehouse = line.order_id.warehouse_id
            if not warehouse:
                super(SaleOrderLine, line)._compute_purchase_price()
                continue

            product_variant = line.product_id
            cost_method = product_variant.categ_id.property_cost_method
            wpp = self.env['warehouse.product.price']

            if cost_method == 'fifo':
                line.purchase_price = wpp._get_fifo_unit_cost(
                    product_variant, warehouse, sale_qty=line.product_uom_qty
                )
            else:
                price_record = wpp._get_price_record(product_variant, warehouse)
                line.purchase_price = price_record.cost if price_record else product_variant.standard_price