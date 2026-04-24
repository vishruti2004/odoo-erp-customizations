from odoo import models, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sale_line_id'):
                sale_line = self.env['sale.order.line'].browse(vals['sale_line_id'])
                if sale_line.location_id:
                    vals['location_id'] = sale_line.location_id.id
        return super().create(vals_list)
