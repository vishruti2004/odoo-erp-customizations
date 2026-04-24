from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
    )

    location_domain_ids = fields.Many2many(
        'stock.location',
        compute='_compute_location_domain',
        string='Locations',
    )

    @api.depends('product_id')
    def _compute_location_domain(self):
        for line in self:
            if line.product_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('quantity', '>', 0),
                    ('location_id.usage', '=', 'internal'),
                ])
                line.location_domain_ids = quants.mapped('location_id')
            else:
                line.location_domain_ids = [(5, 0, 0)]

    @api.constrains('product_uom_qty', 'location_id', 'product_id')
    def _check_available_qty(self):
        for line in self:
            if line.location_id and line.product_id:
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', line.location_id.id),
                ], limit=1)
                available = quant.quantity if quant else 0.0
                if line.product_uom_qty > available:
                   raise ValidationError(
                        f"stock not available in '{line.location_id.display_name}' "
                        f"Only {available} qty available select a different location."
                    )