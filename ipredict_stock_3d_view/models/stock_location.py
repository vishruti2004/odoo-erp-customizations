# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, fields, models, _

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

    rotation_y = fields.Float(
        string="Rotation (°)",
        default=0.0,
        help="Rotate rack around Y axis (0-360 degrees). 0 = front, 90 = side."
    )

    shelf_levels = fields.Integer(string="Shelf Levels", default=3)
    bins_per_level = fields.Integer(string="Bins per Level", default=5)

    capacity = fields.Float(
        string="Max Weight",
        related='storage_category_id.max_weight',
        readonly=True,
        store=False,
    )

    color_upright = fields.Char(string="Upright Color", default="#4F6489")
    color_beam = fields.Char(string="Beam Color", default="#F4C842")
    color_slat = fields.Char(string="Slat Color", default="#D5D5D5")
    color_box = fields.Char(string="Stock Box Color", default="#E8C89A")

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
        compute_sudo=True,
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
    #  COMPUTE: Slot grid JSON
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

            children = self.env['stock.location'].search([
                ('location_id', '=', loc.id),
                ('usage', 'in', ['internal', 'view']),
            ], order='complete_name')

            children_list = [{
                'id': c.id,
                'name': c.name,
                'complete_name': c.complete_name,
            } for c in children]

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
    #  ACTION: Toggle single slot
    # ============================================================
    def action_toggle_slot(self, level, bin, child_id):
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
            if existing:
                existing.unlink()
            return False

        if existing and existing.location_id.id == child_id:
            existing.unlink()
            return False

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
    #  ACTION: Bulk assign/unassign
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
                if existing and (not child_id or existing.location_id.id == child_id):
                    existing.unlink()
            else:
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
    #  ACTION: Move whole slot (swap safe)
    # ============================================================
    def action_move_slot(self, from_level, from_bin, to_level, to_bin, product_location_id=None):
        self.ensure_one()
        if not self.show_in_3d:
            return False

        if (to_level < 0 or to_level >= (self.shelf_levels or 0)
                or to_bin < 0 or to_bin >= (self.bins_per_level or 0)):
            return False

        Slot = self.env['stock.location.rack.slot']

        src = Slot.search([
            ('parent_rack_id', '=', self.id),
            ('level', '=', from_level),
            ('bin', '=', from_bin),
        ], limit=1)

        if not src:
            loc_id = product_location_id
            if not loc_id:
                quants = self.env['stock.quant'].search([
                    ('location_id', '=', self.id), ('quantity', '>', 0)])
                if quants:
                    loc_id = self.id
            if not loc_id:
                return False

            existing = Slot.search([
                ('parent_rack_id', '=', self.id),
                ('location_id', '=', loc_id),
            ], limit=1)
            if existing:
                src = existing
            else:
                src = Slot.create({
                    'parent_rack_id': self.id,
                    'location_id': loc_id,
                    'level': from_level,
                    'bin': from_bin,
                })

        target = Slot.search([
            ('parent_rack_id', '=', self.id),
            ('level', '=', to_level),
            ('bin', '=', to_bin),
        ], limit=1)

        if target and target.id != src.id:
            TMP_LEVEL = 9999
            TMP_BIN = 9999
            src.write({'level': TMP_LEVEL, 'bin': TMP_BIN})
            self.env.cr.flush()
            target.write({'level': from_level, 'bin': from_bin})
            self.env.cr.flush()
            src.write({'level': to_level, 'bin': to_bin})
        else:
            src.write({'level': to_level, 'bin': to_bin})

        return True

    # ============================================================
    #  ACTION: Move SINGLE BOX (quant) — same rack only
    # ============================================================
    @api.model
    def action_move_box_3d(self, rack_id, quant_id, from_level, from_bin, to_level, to_bin):
        """Move a SINGLE quant (one box) to a target slot within the SAME rack."""
        rack = self.browse(rack_id)
        if not rack.exists():
            return False

        Quant = self.env['stock.quant']
        Slot = self.env['stock.location.rack.slot']
        Location = self.env['stock.location']

        src_quant = Quant.browse(quant_id)
        if not src_quant.exists():
            return False

        src_loc = src_quant.location_id
        is_descendant = (
            src_loc.id == rack_id
            or src_loc.location_id.id == rack_id
            or src_loc.location_id.location_id.id == rack_id
        )
        if not is_descendant:
            return False

        if (to_level < 0 or to_level >= (rack.shelf_levels or 0)
                or to_bin < 0 or to_bin >= (rack.bins_per_level or 0)):
            return False

        tgt_slot = Slot.search([
            ('parent_rack_id', '=', rack_id),
            ('level', '=', to_level),
            ('bin', '=', to_bin),
        ], limit=1)

        if not tgt_slot:
            src_slot = Slot.search([
                ('parent_rack_id', '=', rack_id),
                ('level', '=', from_level),
                ('bin', '=', from_bin),
            ], limit=1)
            child_name = (src_slot.location_id.name if src_slot
                          else (rack.code_3d or rack.name))
            new_child = Location.create({
                'name': child_name,
                'location_id': rack_id,
                'usage': 'internal',
            })
            tgt_slot = Slot.create({
                'parent_rack_id': rack_id,
                'location_id': new_child.id,
                'level': to_level,
                'bin': to_bin,
            })

        src_quant.write({'location_id': tgt_slot.location_id.id})

        if from_level is not None and from_bin is not None:
            src_slot_del = Slot.search([
                ('parent_rack_id', '=', rack_id),
                ('level', '=', from_level),
                ('bin', '=', from_bin),
            ], limit=1)
            if src_slot_del:
                remaining = Quant.search_count([
                    ('location_id', '=', src_slot_del.location_id.id),
                    ('quantity', '>', 0),
                ])
                if remaining == 0:
                    child = src_slot_del.location_id
                    src_slot_del.unlink()
                    if (child and child.location_id.id == rack_id
                            and Quant.search_count([
                                ('location_id', '=', child.id),
                                ('quantity', '>', 0),
                            ]) == 0):
                        child.unlink()
        return True

    # ============================================================
    #  COMPUTE: Stock data
    # ============================================================
    @api.depends('storage_category_id', 'storage_category_id.max_weight')
    def _compute_3d_stock_data(self):
        Quant = self.env['stock.quant']
        for loc in self:
            quants = Quant.search([
                ('location_id', '=', loc.id),
                ('quantity', '>', 0),
            ])
            total = sum(quants.mapped('quantity'))
            loc.on_hand = total

            max_weight = loc.capacity or 0.0
            loc.fill_percentage = (
                min(100.0, (total / max_weight) * 100)
                if max_weight > 0 else 0.0
            )
            loc.product_ids = [(6, 0, quants.mapped('product_id').ids)]

    # ============================================================
    #  HELPER: Find warehouse for a location
    # ============================================================
    def _find_warehouse(self, loc):
        """Walk up to find warehouse root."""
        current = loc
        depth = 0
        while current.location_id and depth < 10:
            current = current.location_id
            depth += 1

        wh = self.env['stock.warehouse'].search([
            ('view_location_id', '=', current.id),
        ], limit=1)
        if wh:
            return wh

        if loc.warehouse_id:
            return loc.warehouse_id
        return None

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
            'quant_id': q.id,
            'name': q.product_id.name,
            'qty': q.quantity,
            'color': q.product_id.color or '#3498db',
            'image_url': '/web/image/product.product/%s/image_128' % q.product_id.id,

        } for q in quants]

        children = Location.search([
            ('location_id', '=', loc.id),
            ('usage', 'in', ['internal', 'view']),
        ], order='complete_name')

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
                'quant_id': q.id,
                'name': q.product_id.name,
                'qty': q.quantity,
                'color': q.product_id.color or '#3498db',
                'image_url': '/web/image/product.product/%s/image_128' % q.product_id.id,

            } for q in child_quants]

            slots.append({
                'level': s.level,
                'bin': s.bin,
                'location_id': child_loc.id,
                'location_name': child_loc.name,
                'complete_name': child_loc.complete_name,
                'products': child_products,
            })

        if not slots and products:
            slots.append({
                'level': 0,
                'bin': 0,
                'location_id': loc.id,
                'location_name': loc.name,
                'complete_name': loc.complete_name,
                'products': products,
            })

        # Warehouse info
        wh = self._find_warehouse(loc)
        warehouse_id = wh.id if wh else False
        warehouse_name = wh.name if wh else 'Unassigned'

        return {
            'id': loc.id,
            'name': loc.name,
            'complete_name': loc.complete_name,
            'code_3d': loc.code_3d or loc.name,
            'pos_x': loc.pos_x,
            'pos_y': loc.pos_y,
            'pos_z': loc.pos_z,
            'rotation_y': loc.rotation_y or 0.0,
            'rack_length': loc.rack_length,
            'rack_width': loc.rack_width,
            'rack_height': loc.rack_height,
            'shelf_levels': loc.shelf_levels,
            'bins_per_level': loc.bins_per_level,
            'capacity': loc.capacity or 0.0,
            'storage_category_id': loc.storage_category_id.id or False,
            'storage_category_name': loc.storage_category_id.name or '',
            'on_hand': loc.on_hand,
            'fill_percentage': loc.fill_percentage,
            'color_upright': loc.color_upright,
            'color_beam': loc.color_beam ,
            'color_slat': loc.color_slat,
            'color_box': loc.color_box ,
            'beam_height': loc.beam_height or 0.16,
            'slots': slots,
            'products': products,
            'warehouse_id': warehouse_id,
            'warehouse_name': warehouse_name,
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

        # Extract unique warehouses
        warehouses = {}
        for l in locations:
            wid = l.get('warehouse_id')
            wname = l.get('warehouse_name') or 'Unassigned'
            if wid:
                warehouses[wid] = wname
            else:
                warehouses[0] = 'Unassigned'

        all_products = self.env['product.product'].search([])
        return {
            'locations': locations,
            'warehouses': [{'id': k, 'name': v} for k, v in warehouses.items()],
            'products': [{
                'id': p.id,
                'name': p.name,
                'color': p.color or '#3498db',
            } for p in all_products],
        }

    # ============================================================
    #  ADD RACK PANEL — Available locations
    # ============================================================
    @api.model
    def get_available_locations_for_3d(self):
        locations = self.search([
            ('usage', '=', 'internal'),
        ], order='complete_name')
        result = []
        for loc in locations:
            wh = self._find_warehouse(loc)
            result.append({
                'id': loc.id,
                'name': loc.name,
                'complete_name': loc.complete_name,
                'show_in_3d': loc.show_in_3d,
                'warehouse_id': wh.id if wh else 0,
                'warehouse_name': wh.name if wh else 'Unassigned',
            })
        return result

    # ============================================================
    #  MOVE RACK IN 3D — Save new X/Z position
    # ============================================================
    @api.model
    def action_move_rack_3d(self, location_id, pos_x, pos_z):
        loc = self.browse(location_id)
        if not loc.exists():
            return False
        loc.write({
            'pos_x': float(pos_x),
            'pos_z': float(pos_z),
        })
        return True

    # ============================================================
    #  ADD/EDIT RACK — Setup 3D params
    # ============================================================
    @api.model
    def setup_rack_3d(self, location_id, params):
        loc = self.browse(location_id)
        if not loc.exists():
            return {'error': 'Location not found'}

        vals = {
            'show_in_3d': True,
            'pos_x': params.get('pos_x', 0.0),
            'pos_y': 0.0,
            'pos_z': params.get('pos_z', 0.0),
            'rotation_y': params.get('rotation_y', 0.0),
            'rack_length': params.get('rack_length', 3.0),
            'rack_width': params.get('rack_width', 1.2),
            'rack_height': params.get('rack_height', 3.0),
            'shelf_levels': params.get('shelf_levels', 3),
            'bins_per_level': params.get('bins_per_level', 5),
        }
        loc.write(vals)

        return {
            'id': loc.id,
            'name': loc.name,
            'complete_name': loc.complete_name,
            'capacity': loc.capacity or 0.0,
        }

    # ============================================================
    #  DELETE RACK — Remove from 3D + DB
    # ============================================================
    @api.model
    def delete_rack_from_3d(self, location_id):
        loc = self.browse(location_id)
        if not loc.exists():
            return {'error': 'Location not found'}

        try:
            quant_count = self.env['stock.quant'].search_count([
                ('location_id', '=', loc.id),
                ('quantity', '>', 0),
            ])

            child_locs = self.env['stock.location'].search([
                ('location_id', '=', loc.id),
            ])
            for child in child_locs:
                child_quants = self.env['stock.quant'].search_count([
                    ('location_id', '=', child.id),
                    ('quantity', '>', 0),
                ])
                if child_quants > 0:
                    return {
                        'error': f'Cannot delete: "{child.complete_name}" has stock. '
                                 f'Move or remove products first.'
                    }
                self.env['stock.location.rack.slot'].search([
                    ('parent_rack_id', '=', child.id),
                ]).unlink()
                child.unlink()

            if quant_count > 0:
                return {
                    'error': f'Cannot delete: "{loc.complete_name}" has stock. '
                             f'Move or remove products first.'
                }

            self.env['stock.location.rack.slot'].search([
                ('parent_rack_id', '=', loc.id),
            ]).unlink()

            loc.unlink()

            return {'success': True}

        except Exception as e:
            _logger.exception("Error deleting rack %s: %s", loc.complete_name, e)
            return {'error': str(e)}

    def action_view_location_products_3d(self):
        self.ensure_one()

       
        action = self.env['ir.actions.actions']._for_xml_id(
            'stock.act_product_location_open'
        )

        # Pass the selected 3D location to the standard Odoo product view.
        action['context'] = {
            'location': self.id,
            'active_id': self.id,
            'active_model': 'stock.location',

            'search_default_real_stock_available': 1,
            'search_default_virtual_stock_available': 1,
            'search_default_virtual_stock_negative': 1,
            'search_default_real_stock_negative': 1,

            'create': False,
        }

        action['name'] = 'Products'
        action['target'] = 'current'

        return action