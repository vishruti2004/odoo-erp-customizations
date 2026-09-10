# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class StockLocationRackSlot(models.Model):
    _name = 'stock.location.rack.slot'
    _description = 'Rack Slot Assignment'
    _order = 'level, bin'

    location_id = fields.Many2one(
        'stock.location', string="Child Location",
        required=True, ondelete='cascade', index=True,
    )
    parent_rack_id = fields.Many2one(
        'stock.location', string="Parent Rack",
        required=True, ondelete='cascade', index=True,
    )
    level = fields.Integer(string="Level", required=True)
    bin = fields.Integer(string="Bin", required=True)

    _unique_slot = models.Constraint(
        'UNIQUE(parent_rack_id, level, bin)',
        'Aa slot already assigned che bija child ne!'
    )


class StockLocation(models.Model):
    _inherit = 'stock.location'

    # ---- 3D Visibility ----
    show_in_3d = fields.Boolean(string="Show in 3D View", default=False)
    code_3d = fields.Char(string="3D Label Code")

    pos_x = fields.Float(string="Position X", default=0.0)
    pos_y = fields.Float(string="Position Y (Height)", default=0.0)
    pos_z = fields.Float(string="Position Z", default=0.0)

    rack_length = fields.Float(string="Rack Length (X)", default=3.0)
    rack_width = fields.Float(string="Rack Width (Z)", default=1.2)
    rack_height = fields.Float(string="Rack Height (Y)", default=3.0)

    shelf_levels = fields.Integer(string="Shelf Levels", default=3)
    bins_per_level = fields.Integer(string="Bins per Level", default=5)
    capacity = fields.Float(string="Max Capacity (units)", default=1000.0)

    color_upright = fields.Char(string="Upright Color", default="#4F6489")
    color_beam = fields.Char(string="Beam Color", default="#F4C842")
    color_slat = fields.Char(string="Slat Color", default="#D5D5D5")
    color_box = fields.Char(string="Stock Box Color", default="#E8C89A")

    post_thickness = fields.Float(string="Upright Thickness", default=0.09)
    beam_height = fields.Float(string="Beam Height", default=0.16)

    # ---- Slots ----
    rack_slot_ids = fields.One2many(
        'stock.location.rack.slot', 'parent_rack_id',
        string="Slots in this rack",
    )
    rack_children_ids = fields.One2many(
        'stock.location', 'location_id',
        string="Child Locations",
    )
    slot_grid_json = fields.Char(
        string="Slot Grid",
        compute="_compute_slot_grid_json",
    )

    on_hand = fields.Float(string="On Hand",
        compute="_compute_3d_stock_data", compute_sudo=True)
    fill_percentage = fields.Float(string="Fill %",
        compute="_compute_3d_stock_data", compute_sudo=True)
    product_ids = fields.Many2many(
        'product.product', string="Products Stored",
        compute="_compute_3d_stock_data", compute_sudo=True,
    )

    # ============================================================
    #  COMPUTE: Slot grid for THIS location (as rack)
    # ============================================================
    @api.depends('show_in_3d', 'shelf_levels', 'bins_per_level',
                 'rack_slot_ids', 'rack_slot_ids.level',
                 'rack_slot_ids.bin', 'rack_slot_ids.location_id',
                 'rack_children_ids')
    def _compute_slot_grid_json(self):
        for loc in self:
            if not loc.show_in_3d:
                loc.slot_grid_json = '{}'
                continue

            levels = loc.shelf_levels or 0
            bins = loc.bins_per_level or 0

            # Children (parts)
            children = self.env['stock.location'].search([
                ('location_id', '=', loc.id),
                ('usage', 'in', ['internal', 'view']),
            ], order='complete_name')

            children_list = [{
                'id': c.id,
                'name': c.name,
                'complete_name': c.complete_name,
            } for c in children]

            # Slots in this rack
            slots = [{
                'level': s.level,
                'bin': s.bin,
                'child_id': s.location_id.id,
                'child_name': s.location_id.name,
            } for s in loc.rack_slot_ids]

            loc.slot_grid_json = json.dumps({
                'levels': levels,
                'bins': bins,
                'children': children_list,
                'slots': slots,
            })

    # ============================================================
    #  ACTION: Toggle a slot (assign/unassign child to cell)
    # ============================================================
    def action_toggle_slot(self, level, bin, child_id):
        """Assign/unassign child at (level, bin) in this rack."""
        self.ensure_one()
        if not self.show_in_3d:
            return False

        Slot = self.env['stock.location.rack.slot']

        existing = Slot.search([
            ('parent_rack_id', '=', self.id),
            ('level', '=', level),
            ('bin', '=', bin),
        ])

        if not child_id:
            # Unassign (clear)
            if existing:
                existing.unlink()
            return False

        # If same child already there → unassign
        if existing and existing.location_id.id == child_id:
            existing.unlink()
            return False

        # If different child → replace
        if existing:
            existing.unlink()

        Slot.create({
            'parent_rack_id': self.id,
            'location_id': child_id,
            'level': level,
            'bin': bin,
        })
        return True

        # ============================================================
    #  ACTION: Bulk assign/unassign (row toggle)
    # ============================================================
    def action_bulk_slots(self, cells, child_id, assign):
    
        self.ensure_one()
        if not self.show_in_3d:
            return False

        Slot = self.env['stock.location.rack.slot']

        for level, bin in cells:
            existing = Slot.search([
                ('parent_rack_id', '=', self.id),
                ('level', '=', level),
                ('bin', '=', bin),
            ], limit=1)

            if not assign:
                # Unassign — only if it belongs to child_id (or no child specified)
                if existing and (not child_id or existing.location_id.id == child_id):
                    existing.unlink()
            else:
                # Assign — replace if different, create if empty
                if child_id:
                    if existing:
                        if existing.location_id.id != child_id:
                            existing.unlink()
                            Slot.create({
                                'parent_rack_id': self.id,
                                'location_id': child_id,
                                'level': level,
                                'bin': bin,
                            })
                    else:
                        Slot.create({
                            'parent_rack_id': self.id,
                            'location_id': child_id,
                            'level': level,
                            'bin': bin,
                        })
        return True

    # ============================================================
    #  COMPUTE: Stock data
    # ============================================================
    @api.depends('capacity')
    def _compute_3d_stock_data(self):
        Quant = self.env['stock.quant']
        for loc in self:
            quants = Quant.search([
                ('location_id', '=', loc.id),
                ('quantity', '>', 0),
            ])
            total = sum(quants.mapped('quantity'))
            loc.on_hand = total
            loc.fill_percentage = (
                min(100.0, (total / loc.capacity) * 100)
                if loc.capacity > 0 else 0.0
            )
            loc.product_ids = [(6, 0, quants.mapped('product_id').ids)]

    # ============================================================
    #  SERIALIZE for 3D
    # ============================================================
    def _serialize_location(self, loc, depth=0):
        if depth > 10:
            return None

        Location = self.env['stock.location']
        Quant = self.env['stock.quant']

        quants = Quant.search([
            ('location_id', '=', loc.id), ('quantity', '>', 0)])
        products = [{
            'id': q.product_id.id,
            'name': q.product_id.name,
            'qty': q.quantity,
            'color': q.product_id.color or '#3498db',
        } for q in quants]

        children = Location.search([
            ('location_id', '=', loc.id),
            ('usage', 'in', ['internal', 'view']),
        ], order='complete_name')

        # ------------------------------------------------------------
        # IMPORTANT FIX: previously this only sent [level, bin] pairs,
        # with NO information about which child location was assigned
        # to that slot, and NO information about what stock (products)
        # that child location actually holds. The frontend therefore
        # had no way to:
        #   1) label a bin with the assigned location's name, or
        #   2) know whether that bin actually has stock (to decide
        #      whether to render a product box at all).
        #
        # Now each slot carries the assigned child's id/name AND that
        # child's own current stock (quants), fetched directly here.
        # ------------------------------------------------------------
        slots = []
        for s in loc.rack_slot_ids:
            child_loc = s.location_id
            if not child_loc:
                continue

            child_quants = Quant.search([
                ('location_id', '=', child_loc.id),
                ('quantity', '>', 0),
            ])
            child_products = [{
                'id': q.product_id.id,
                'name': q.product_id.name,
                'qty': q.quantity,
                'color': q.product_id.color or '#3498db',
            } for q in child_quants]

            slots.append({
                'level': s.level,
                'bin': s.bin,
                'location_id': child_loc.id,
                'location_name': child_loc.name,
                'complete_name': child_loc.complete_name,
                'products': child_products,
            })

        return {
            'id': loc.id,
            'name': loc.name,
            'complete_name': loc.complete_name,
            'code_3d': loc.code_3d or loc.name,

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

            'color_upright': loc.color_upright or '#4F6489',
            'color_beam': loc.color_beam or '#F4C842',
            'color_slat': loc.color_slat or '#D5D5D5',
            'color_box': loc.color_box or '#E8C89A',
            'post_thickness': loc.post_thickness or 0.09,
            'beam_height': loc.beam_height or 0.16,

            'slots': slots,
            'products': products,
            'children': [c for c in (
                self._serialize_location(ch, depth + 1) for ch in children
            ) if c is not None],
        }

    def get_3d_data(self, ids=None, **kwargs):
        roots = self.search([
            ('show_in_3d', '=', True),
            ('usage', '=', 'internal'),
        ])
        locations = []
        for loc in roots:
            try:
                loc._compute_3d_stock_data()
                s = self._serialize_location(loc, 0)
                if s:
                    locations.append(s)
            except Exception as e:
                _logger.exception("Error serializing %s: %s",
                                  loc.complete_name, e)

        all_products = self.env['product.product'].search([])
        return {
            'locations': locations,
            'products': [{
                'id': p.id,
                'name': p.name,
                'color': p.color or '#3498db',
            } for p in all_products],
        }