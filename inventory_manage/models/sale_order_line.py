from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    location_id = fields.Many2one(
        'stock.location',
        string='Source Location',
    )

    location_ids = fields.Many2many(
        'stock.location',
        string='Locations',
    )

    location_domain_ids = fields.Many2many(
        'stock.location',
        compute='_compute_location_domain',
        string='Available Locations',
    )

    sp_commission_amount = fields.Monetary(
        string="Sale Person Commission", 
        compute="_compute_sp_commission", 
        store=True,
        currency_field='currency_id'
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

    @api.constrains('location_ids', 'product_uom_qty', 'product_id')
    def _check_available_qty(self):
        for line in self:
            if not line.location_ids or not line.product_id:
                continue
            total_available = sum(
                self.env['stock.quant'].search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', loc.id),
                ], limit=1).available_quantity
                for loc in line.location_ids
            )
            if line.product_uom_qty > total_available:
                raise ValidationError(
                    f"Not enough stock for '{line.product_id.name}'. "
                    f"Only {total_available} available."
                )
            
    @api.depends('price_subtotal', 'product_uom_qty', 'order_id.pricelist_id', 'product_id')    
    def _compute_sp_commission(self):
        for line in self:
            if line.pricelist_item_id and line.pricelist_item_id.allow_discount:
                percentage = line.pricelist_item_id.discount_percentage
                line.sp_commission_amount = (line.price_subtotal * (percentage / 100.0))
            else:
                line.sp_commission_amount = 0.0