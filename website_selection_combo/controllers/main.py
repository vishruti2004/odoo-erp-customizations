# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class WebsiteSelectionComboController(http.Controller):

    @http.route('/website_selection_combo/check_combo', type='json', auth='public', methods=['POST'], csrf=False)
    def check_combo(self, **kwargs):
        try:
            product_tmpl_id = kwargs.get('product_tmpl_id')
            if not product_tmpl_id:
                return {'is_combo': False, 'error': 'product_tmpl_id required'}

            product = request.env['product.template'].sudo().browse(int(product_tmpl_id))
            if not product.exists():
                return {'is_combo': False, 'error': 'Product not found'}

            return {
                'is_combo': bool(product.selection_combo),
                'has_lines': bool(product.selection_combo_line_ids),
                'product_name': product.name,
                'product_id': product.id,
                'combo_lines_count': len(product.selection_combo_line_ids),
            }
        except Exception as e:
            _logger.error("check_combo ERROR: %s", str(e), exc_info=True)
            return {'is_combo': False, 'error': str(e)}

    @http.route('/website_selection_combo/get_combo_data', type='json', auth='public', methods=['POST'], csrf=False)
    def get_combo_data(self, **kwargs):
        try:
            product_tmpl_id = kwargs.get('product_tmpl_id')
            if not product_tmpl_id:
                return {'error': 'product_tmpl_id required'}

            product = request.env['product.template'].sudo().browse(int(product_tmpl_id))
            if not product.exists():
                return {'error': 'Product not found'}
            if not product.selection_combo:
                return {'error': 'Product is not a combo'}

            combos = [{
                'id': line.id,
                'category_name': line.product_public_category_id.name,
                'combo_items': [{
                    'id': p.id,
                    'product_id': p.id,
                    'product_tmpl_id': p.product_tmpl_id.id,
                    'product_name': p.name,
                    'extra_price': float(p.list_price or 0.0),
                    'image_url': f'/web/image/product.product/{p.id}/image_128',
                } for p in line.product_ids],
                'minimum_selection': line.minimum_selection,
                'maximum_selection': line.maximum_selection,
                'allow_multiple_selection': line.allow_multiple_selection,
                'include_selected_product_price': line.include_selected_product_price,
            } for line in product.selection_combo_line_ids]

            return {
                'display_name': product.name,
                'combos': combos,
                'currency_id': request.env.company.currency_id.id,
                'base_price': float(product.list_price or 0.0),
            }
        except Exception as e:
            _logger.error("get_combo_data ERROR: %s", str(e), exc_info=True)
            return {'error': str(e)}

    @http.route('/website_selection_combo/get_order_line_data', type='json', auth='public', methods=['POST'], csrf=False)
    def get_order_line_data(self, **kwargs):
        try:
            line_id = kwargs.get('line_id')
            if not line_id:
                return {'error': 'line_id required'}

            order_line = request.env['sale.order.line'].sudo().browse(int(line_id))
            if not order_line.exists():
                return {'error': 'Order line not found'}

            product = order_line.product_id.product_tmpl_id
            combos = [{
                'id': line.id,
                'category_name': line.product_public_category_id.name,
                'combo_items': [{
                    'id': p.id,
                    'product_id': p.id,
                    'product_name': p.name,
                    'extra_price': float(p.list_price or 0.0),
                    'image_url': f'/web/image/product.product/{p.id}/image_128',
                } for p in line.product_ids],
                'minimum_selection': line.minimum_selection,
                'maximum_selection': line.maximum_selection,
                'allow_multiple_selection': line.allow_multiple_selection,
                'include_selected_product_price': line.include_selected_product_price,
            } for line in product.selection_combo_line_ids]

            selected_items = [{
                'product_id': sel.product_id.id,
                'product_name': sel.product_id.name,
                'quantity': sel.quantity,
                'extra_price': sel.extra_price,
            } for sel in order_line.combo_selection_ids]

            return {
                'product_id': order_line.product_id.id,
                'product_tmpl_id': product.id,
                'display_name': order_line.product_id.name,
                'combos': combos,
                'selected_items': selected_items,
                'currency_id': request.env.company.currency_id.id,
                'base_price': order_line.product_id.list_price or 0.0,
                'quantity': order_line.product_uom_qty,
                'is_combo_line': bool(order_line.combo_selection_ids),
            }
        except Exception as e:
            _logger.error("get_order_line_data ERROR: %s", str(e), exc_info=True)
            return {'error': str(e)}

    @http.route('/website_selection_combo/update_order_line', type='json', auth='public', methods=['POST'], csrf=False)
    def update_order_line(self, **kwargs):
        try:
            line_id = kwargs.get('line_id')
            selected_items = kwargs.get('selected_items') or []
            quantity = int(kwargs.get('quantity', 1))

            if not line_id:
                return {'error': 'line_id required'}

            order_line = request.env['sale.order.line'].sudo().browse(int(line_id))
            if not order_line.exists():
                return {'error': 'Order line not found'}

            order_line.write({'product_uom_qty': quantity})
            order_line.combo_selection_ids.unlink()

            for item in selected_items:
                request.env['sale.combo.selection'].sudo().create({
                    'order_line_id': order_line.id,
                    'product_id': item.get('product_id'),
                    'quantity': item.get('quantity', 1),
                    'extra_price': item.get('extra_price', 0.0),
                })

            order_line.order_id._update_cart()

            return {
                'success': True,
                'line_id': order_line.id,
                'message': 'Combo updated successfully',
            }
        except Exception as e:
            _logger.error("update_order_line ERROR: %s", str(e), exc_info=True)
            return {'error': str(e)}