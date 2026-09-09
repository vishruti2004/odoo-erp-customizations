# -*- coding: utf-8 -*-
import logging
from odoo import api, fields, models
_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # ---- 3D Properties ----
    show_in_3d = fields.Boolean(
        string="Show in 3D View",
        default=False,
        help="Enable this location to appear in the 3D Warehouse view."
    )
    pos_x = fields.Float(
        string="Position X",
        default=0.0,
        help="X coordinate (left/right) on the floor plan."
    )
    pos_y = fields.Float(
        string="Position Y (Height)",
        default=0.0,
        help="Y coordinate (vertical / height) of the rack base."
    )
    pos_z = fields.Float(
        string="Position Z",
        default=0.0,
        help="Z coordinate (front/back) on the floor plan."
    )
    rack_length = fields.Float(
        string="Rack Length",
        default=2.0,
        help="Length of the rack (X direction)."
    )
    rack_width = fields.Float(
        string="Rack Width",
        default=1.0,
        help="Width of the rack (Z direction)."
    )
    rack_height = fields.Float(
        string="Rack Height",
        default=2.0,
        help="Total height of the rack (Y direction)."
    )
    shelf_levels = fields.Integer(
        string="Shelf Levels",
        default=3,
        help="Number of horizontal shelf levels in this rack."
    )
    bins_per_level = fields.Integer(
        string="Bins per Level",
        default=2,
        help="Number of bins (columns) on each shelf level."
    )
    capacity = fields.Float(
        string="Max Capacity (units)",
        default=100.0,
        help="Maximum storage capacity in units (e.g., kilograms, pallets)."
    )

    # ---- Computed Fields (for 3D) ----
    on_hand = fields.Float(
        string="On Hand",
        compute="_compute_3d_stock_data",
        help="Current quantity in this location."
    )
    fill_percentage = fields.Float(
        string="Fill %",
        compute="_compute_3d_stock_data",
        help="Percentage of capacity filled (0-100)."
    )
    product_ids = fields.Many2many(
        'product.product',
        string="Products Stored",
        compute="_compute_3d_stock_data",
        help="Products currently stored in this location."
    )

    @api.depends('capacity')
    def _compute_3d_stock_data(self):
        """Fetch stock.quant data for each location."""
        Quant = self.env['stock.quant']

        for loc in self:
            _logger.info("===== Computing 3D stock data for location: %s (ID: %s) =====", loc.display_name, loc.id)

            quants = Quant.search([
                ('location_id', '=', loc.id),
                ('quantity', '>', 0)
            ])

            total_on_hand = sum(quants.mapped('quantity'))
            loc.on_hand = total_on_hand

            if loc.capacity > 0:
                loc.fill_percentage = min(100.0, (total_on_hand / loc.capacity) * 100)
            else:
                loc.fill_percentage = 0.0

            products = quants.mapped('product_id')
            loc.product_ids = [(6, 0, products.ids)]

            _logger.info("Location: %s | Total quants: %d | On hand: %.2f | Products: %d",
                         loc.display_name, len(quants), total_on_hand, len(products))
            for quant in quants:
                _logger.info("  Quant: Product: %s (ID: %s) | Quantity: %.2f",
                             quant.product_id.display_name, quant.product_id.id, quant.quantity)

    # ---- API method for 3D frontend ----
    def get_3d_data(self, ids=None, **kwargs):
        """Return all 3D data (locations + stock) as JSON."""
        _logger.info("===== get_3d_data called: fetching 3D locations =====")

        locations = self.search([
            ('show_in_3d', '=', True),
            ('usage', '=', 'internal')
        ])

        _logger.info("Found %d location(s) with show_in_3d=True", len(locations))

        result = {
            'locations': [],
            'products': [],
        }

        all_products = self.env['product.product'].search([])
        product_map = {}
        for prod in all_products:
            product_map[prod.id] = {
                'id': prod.id,
                'name': prod.name,
                'color': prod.color or '#3498db',
                'uom': prod.uom_id.name,
            }

        for loc in locations:
            _logger.info("Processing location: %s (ID: %s)", loc.display_name, loc.id)
            loc._compute_3d_stock_data()

            # For debugging: log the product_ids after compute
            _logger.info("Location %s: product_ids = %s", loc.display_name, loc.product_ids.ids)

            result['locations'].append({
                'id': loc.id,
                'name': loc.name,
                'complete_name': loc.complete_name,
                'pos_x': loc.pos_x,
                'pos_y': loc.pos_y,
                'pos_z': loc.pos_z,
                'rack_length': loc.rack_length,
                'rack_width': loc.rack_width,
                'rack_height': loc.rack_height,
                'shelf_levels': loc.shelf_levels,
                'bins_per_level': loc.bins_per_level,
                'capacity': loc.capacity,
                'on_hand': loc.on_hand,
                'fill_percentage': loc.fill_percentage,
                'product_ids': loc.product_ids.ids,
            })

        result['products'] = list(product_map.values())

        _logger.info("get_3d_data returning %d locations, %d products",
                     len(result['locations']), len(result['products']))
        return result