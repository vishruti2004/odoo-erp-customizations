from odoo import models, fields, api

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    location_dest_id = fields.Many2one(
        'stock.location',
        string=' Location',
        domain=[('usage', '=', 'internal')],
    )

    location_domain_ids = fields.Many2many(
        'stock.location',
        compute='_compute_location_domain',
        string=' Locations',
    )

    @api.depends('product_id')
    def _compute_location_domain(self):
        for line in self:
            if not line.product_id:
                line.location_domain_ids = self.env['stock.location']
                continue

            # locations product exists
            product_locs = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id.usage', '=', 'internal'),
            ]).mapped('location_id')

            # Get all empty internal locations
            all_internal = self.env['stock.location'].search([('usage', '=', 'internal'), ('active', '=', True)])
            empty_locs = all_internal - self.env['stock.quant'].search([('quantity', '>', 0), ('location_id.usage', '=', 'internal')]).mapped('location_id')

            line.location_domain_ids = product_locs | empty_locs