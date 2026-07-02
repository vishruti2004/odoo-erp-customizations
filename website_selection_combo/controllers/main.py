# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

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
            combos = []
            for line in product.selection_combo_line_ids:
                combo_items = []
                for p in line.product_ids:
                    combo_items.append({
                        'id': p.id,
                        'product_id': p.id,
                        'product_tmpl_id': p.product_tmpl_id.id,
                        'product_name': p.name,
                        'extra_price': float(p.list_price or 0.0),
                        'image_url': f'/web/image/product.product/{p.id}/image_128',
                    })
                combos.append({
                    'id': line.id,
                    'category_name': line.product_public_category_id.name,
                    'combo_items': combo_items,
                    'minimum_selection': line.minimum_selection,
                    'maximum_selection': line.maximum_selection,
                    'allow_multiple_selection': line.allow_multiple_selection,
                    'include_selected_product_price': line.include_selected_product_price,
                })
            return {
                'display_name': product.name,
                'combos': combos,
                'currency_id': request.env.company.currency_id.id,
                'base_price': float(product.list_price or 0.0),
            }
        except Exception as e:
            return {'error': str(e)}