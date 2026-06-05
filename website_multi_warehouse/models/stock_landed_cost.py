from odoo import models

class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    def button_validate(self):
        result = super().button_validate()
        for landed_cost in self:
            for picking in landed_cost.picking_ids:
                warehouse = (
                    picking.location_dest_id.warehouse_id
                    or picking.picking_type_id.warehouse_id
                )
                if not warehouse:
                    continue

                for stock_move in picking.move_ids:
                    product_variant = stock_move.product_id
                    cost_method = product_variant.categ_id.property_cost_method

                    additional_cost = next((
                        v.additional_landed_cost
                        for v in landed_cost.valuation_adjustment_lines
                        if v.move_id.id == stock_move.id and v.quantity > 0
                    ), 0.0)

                    if not additional_cost:
                        continue

                    price_record = self.env['warehouse.product.price']._get_price_record(
                        product_variant, warehouse
                    )
                    if not price_record:
                        continue

                    if cost_method == 'fifo':
                        fifo_unit_cost = self.env['warehouse.product.price']._get_fifo_unit_cost(
                            product_variant, warehouse
                        )
                        if fifo_unit_cost:
                            price_record.cost = fifo_unit_cost

                    elif cost_method == 'average':
                        stock_quants = self.env['stock.quant'].search([
                            ('product_id', '=', product_variant.id),
                            ('location_id', 'child_of', warehouse.lot_stock_id.id),
                        ])
                        total_qty = sum(stock_quants.mapped('quantity'))
                        if total_qty > 0:
                            price_record.cost += additional_cost / total_qty

                    else:
                        if stock_move.product_uom_qty > 0:
                            price_record.cost += additional_cost / stock_move.product_uom_qty

        return result