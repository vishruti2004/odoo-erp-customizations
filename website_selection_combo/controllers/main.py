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

            product = request.env['product.template'].browse(int(product_tmpl_id))
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

            product = request.env['product.template'].browse(int(product_tmpl_id))
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
            } for line in product.selection_combo_line_ids]

            return {
                'display_name': product.name,
                'combos': combos,
                'currency_id': request.env.company.currency_id.id,
                'base_price': float(product.list_price or 0.0),
                'include_combo_items_price': product.include_combo_items_price,
            }
        except Exception as e:
            _logger.error("get_combo_data ERROR: %s", str(e), exc_info=True)
            return {'error': str(e)}

    @http.route('/website_selection_combo/check_stock', type='json', auth='public', methods=['POST'], csrf=False)
    def check_stock(self, **kwargs):
        try:
            product_ids = kwargs.get('product_ids', [])
            if not product_ids:
                return {'success': True, 'stock_data': {}}

            stock_data = {}
            for product_id in product_ids:
                product = request.env['product.product'].browse(int(product_id))
                if product.exists() and product.is_storable:
                    available_qty = product.qty_available or 0.0
                    stock_data[product_id] = {
                        'available': available_qty,
                        'is_available': available_qty > 0,
                        'name': product.name,
                    }
                else:
                    stock_data[product_id] = {
                        'is_available': True,
                        'name': product.name if product.exists() else 'Unknown',
                    }

            return {
                'success': True,
                'stock_data': stock_data,
            }
        except Exception as e:
            _logger.error("check_stock ERROR: %s", str(e), exc_info=True)
            return {'success': False, 'error': str(e)}

    @http.route('/shop/cart/add', type='jsonrpc', auth='public', methods=['POST'], csrf=False)
    def add_to_cart(self, **kwargs):
        _logger.info(" add_to_cart called with kwargs: %s", kwargs)

        from odoo.addons.website_sale.controllers.main import WebsiteSale
        website_sale = WebsiteSale()

        result = website_sale.add_to_cart(
            product_template_id=kwargs.get('product_template_id'),
            product_id=kwargs.get('product_id'),
            quantity=kwargs.get('quantity', 1.0),
            uom_id=kwargs.get('uom_id'),
            product_custom_attribute_values=kwargs.get('product_custom_attribute_values'),
            no_variant_attribute_value_ids=kwargs.get('no_variant_attribute_value_ids'),
            linked_products=kwargs.get('linked_products'),
            **kwargs
        )

        user_selection = kwargs.get("user_selection")

        if user_selection and result.get('tracking_info'):
            if result['tracking_info']:
                line_id = result['tracking_info'][0].get('item_id')
                if line_id:
                    line = request.env["sale.order.line"].browse(line_id)
                    if line.exists():
                        current_order = request.website.sale_get_order()
                        if current_order and line.order_id.id == current_order.id:
                            line.combo_selection_ids.unlink()
                            for item in user_selection:
                                request.env['sale.combo.selection'].create({
                                    "order_line_id": line.id,
                                    "product_id": item["product_id"],
                                    "quantity": item.get("quantity", 1),
                                    "extra_price": item.get("extra_price", 0),
                                })
        return result

    @http.route('/website_selection_combo/get_order_line_data', type='json', auth='public', methods=['POST'], csrf=False)
    def get_order_line_data(self, **kwargs):
        try:
            line_id = kwargs.get('line_id')
            if not line_id:
                return {'error': 'line_id required'}

            order_line = request.env['sale.order.line'].browse(int(line_id))
            if not order_line.exists():
                return {'error': 'Order line not found'}

            current_order = request.website.sale_get_order()
            if not current_order or order_line.order_id.id != current_order.id:
                return {'error': 'Access denied'}

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
                'include_combo_items_price': product.include_combo_items_price,
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

            order_line = request.env['sale.order.line'].browse(int(line_id))
            if not order_line.exists():
                return {'error': 'Order line not found'}

            current_order = request.website.sale_get_order()
            if not current_order or order_line.order_id.id != current_order.id:
                return {'error': 'Access denied'}

            order_line.write({'product_uom_qty': quantity})
            order_line.combo_selection_ids.unlink()

            for item in selected_items:
                request.env['sale.combo.selection'].create({
                    'order_line_id': order_line.id,
                    'product_id': item['product_id'],
                    'quantity': item.get('quantity', 1),
                    'extra_price': item.get('extra_price', 0.0),
                })
            order_line._update_combo_name()

            order_line.order_id._compute_amounts()

            return {
                'success': True,
                'line_id': order_line.id,
                'price_unit': order_line.price_unit,
                'price_subtotal': order_line.price_subtotal,
                'amount_total': order_line.order_id.amount_total,
                'amount_untaxed': order_line.order_id.amount_untaxed,
                'cart_quantity': order_line.order_id.cart_quantity,
                'message': 'Combo updated successfully',
            }
        except Exception as e:
            _logger.error("update_order_line ERROR: %s", str(e), exc_info=True)
            return {'error': str(e)}