# -*- coding: utf-8 -*-
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    combo_selection_ids = fields.One2many("sale.combo.selection", "order_line_id", copy=True)
    is_combo_line = fields.Boolean(compute="_compute_is_combo_line", store=True)
    combo_total_price = fields.Float(compute="_compute_combo_total_price", store=True, digits='Product Price')

    @api.depends('combo_selection_ids')
    def _compute_is_combo_line(self):
        for line in self:
            line.is_combo_line = bool(line.combo_selection_ids)

    @api.depends('combo_selection_ids', 'combo_selection_ids.quantity', 'combo_selection_ids.extra_price',
                 'product_id', 'product_id.product_tmpl_id.include_combo_items_price')
    def _compute_combo_total_price(self):
        for line in self:
            if not line.combo_selection_ids:
                line.combo_total_price = 0.0
                continue
            base_price = line.product_id.list_price or 0.0
            if line.product_id.product_tmpl_id.include_combo_items_price:
                extra = sum(selection.quantity * selection.extra_price for selection in line.combo_selection_ids)
                line.combo_total_price = base_price + extra
            else:
                line.combo_total_price = base_price

    @api.depends('combo_selection_ids', 'combo_selection_ids.quantity', 'combo_selection_ids.extra_price',
                 'product_id.product_tmpl_id.include_combo_items_price')
    def _compute_price_unit(self):
        super()._compute_price_unit()
        for line in self:
            if not line.combo_selection_ids:
                continue
            base_price = line.product_id.list_price or 0.0
            if line.product_id.product_tmpl_id.include_combo_items_price:
                base_price += sum(selection.quantity * selection.extra_price for selection in line.combo_selection_ids)
            line.price_unit = base_price

    def get_combo_items(self):
        return [{
            'product_id': selection.product_id.id,
            'product_name': selection.product_id.name,
            'quantity': selection.quantity,
            'extra_price': selection.extra_price,
            'image_url': f'/web/image/product.product/{selection.product_id.id}/image_128',
        } for selection in self.combo_selection_ids]

    def _update_combo_name(self):
        for line in self:
            base_lines = [
                line_text for line_text in (line.name or '').split('\n')
                if not line_text.strip().startswith('•')
            ]
            combo_lines = [
                f"• {selection.product_id.name} x {selection.quantity}"
                for selection in line.combo_selection_ids
            ]
            line.name = '\n'.join(base_lines + combo_lines)

    def _prepare_procurement_values(self):
        values = super()._prepare_procurement_values()
        if self.is_combo_line:
            values.update({'combo_items': self.get_combo_items()})
        return values

    def _action_launch_stock_rule(self, *, previous_product_uom_qty=False):
        result = super()._action_launch_stock_rule(previous_product_uom_qty=previous_product_uom_qty)
        for line in self.filtered('combo_selection_ids'):
            line._create_combo_item_moves()
        return result

    def _create_combo_item_moves(self):
        parent_move = self.move_ids.filtered(lambda move: move.state != 'cancel')[:1]
        if not parent_move:
            return

        picking = parent_move.picking_id

        for selection in self.combo_selection_ids:
            product = selection.product_id
            if product.type != 'consu' or not product.is_storable:
                continue

            quantity = selection.quantity * self.product_uom_qty
            if not quantity:
                continue

            existing_move = self.env['stock.move'].sudo().search([
                ('sale_line_id', '=', self.id),
                ('product_id', '=', product.id),
                ('state', '!=', 'cancel'),
            ], limit=1)

            if existing_move:
                existing_move.product_uom_qty = quantity
                continue

            move_vals = {
                'description_picking': f"{product.display_name} (Combo Item)",
                'product_id': product.id,
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'picking_id': picking.id if picking else False,
                'location_id': parent_move.location_id.id,
                'location_dest_id': parent_move.location_dest_id.id,
                'sale_line_id': self.id,
                'company_id': self.company_id.id,
                'picking_type_id': parent_move.picking_type_id.id,
                'reference_ids': [(6, 0, parent_move.reference_ids.ids)],
                'origin': parent_move.origin,
                'state': 'draft',
                'procure_method': 'make_to_stock',
            }
            new_move = self.env['stock.move'].sudo().create(move_vals)
            new_move._action_confirm()
            new_move._action_assign()