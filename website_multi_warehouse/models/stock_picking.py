from odoo import models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        result = super().button_validate()

        for picking in self:
            if picking.picking_type_id.code not in ['incoming', 'outgoing']:
                continue

            warehouse = picking.picking_type_id.warehouse_id
            if not warehouse:
                continue

            for move in picking.move_ids:
                product_product = move.product_id
                product_template = product_product.product_tmpl_id

                cost_method = product_template.categ_id.property_cost_method

                if cost_method == 'fifo':
                    target_cost = product_product.standard_price

                    if picking.picking_type_id.code == 'incoming' and move.price_unit:
                        target_cost = move.price_unit

                else:
                    target_cost = product_product.standard_price

                price_record = self.env['warehouse.product.price'].search([
                    ('product_id', '=', product_template.id),
                    ('warehouse_id', '=', warehouse.id),
                ], limit=1)

                if price_record:
                    price_record.cost = target_cost
                else:
                    self.env['warehouse.product.price'].create({
                        'product_id': product_template.id,
                        'warehouse_id': warehouse.id,
                        'cost': target_cost,
                    })

        return result