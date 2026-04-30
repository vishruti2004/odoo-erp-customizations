from odoo import models, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []

        for vals in vals_list:

            if vals.get('sale_line_id'):
                sale_line = self.env['sale.order.line'].browse(vals['sale_line_id'])
                if sale_line.location_ids:
                    remaining_qty = vals.get('product_uom_qty', 0)
                    for location in sale_line.location_ids:
                        if remaining_qty <= 0:
                            break
                        quant = self.env['stock.quant'].search([
                            ('product_id', '=', sale_line.product_id.id),
                            ('location_id', '=', location.id),
                        ], limit=1)
                        take_qty = min(quant.available_quantity if quant else 0.0, remaining_qty)
                        if take_qty > 0:
                            new_vals = dict(vals)
                            new_vals['location_id'] = location.id
                            new_vals['product_uom_qty'] = take_qty
                            new_vals_list.append(new_vals)
                            remaining_qty -= take_qty
                    continue

            if vals.get('purchase_line_id'):
                purchase_line = self.env['purchase.order.line'].browse(vals['purchase_line_id'])
                if purchase_line.location_dest_id:
                    vals['location_dest_id'] = purchase_line.location_dest_id.id

            new_vals_list.append(vals)

        return super().create(new_vals_list)