from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def cron_check_low_stock(self):
      
        products = self.search([('type', '=', 'consu')]) 

        for product in products:
            company = product.company_id
            
            orderpoint = self.env['stock.warehouse.orderpoint'].search([
                ('product_id', '=', product.id),
                ('company_id', '=', company.id)
            ], limit=1)

            min_qty = orderpoint.product_min_qty if orderpoint else company.low_stock_min_qty

            if min_qty > 0 and product.qty_available <= min_qty:
                managers = company.low_stock_manager_ids
                
                _logger.info(
                    f"LOW STOCK DETECTED | Product: {product.name} | "
                    f"Available: {product.qty_available} | Min: {min_qty}"
                )
                
