# -*- coding: utf-8 -*-
from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _cart_add(
        self,
        product_id,
        quantity=1.0,
        uom_id=None,
        product_custom_attribute_values=None,
        no_variant_attribute_value_ids=None,
        linked_line_id=False,
        combo_item_id=False,
        skip_cart_verification=False,
        **kwargs
    ):
        user_selection = kwargs.pop('user_selection', None)

        result = super()._cart_add(
            product_id=product_id,
            quantity=quantity,
            uom_id=uom_id,
            product_custom_attribute_values=product_custom_attribute_values,
            no_variant_attribute_value_ids=no_variant_attribute_value_ids,
            linked_line_id=linked_line_id,
            combo_item_id=combo_item_id,
            skip_cart_verification=skip_cart_verification,
            **kwargs
        )

        if user_selection and result.get('line_id'):
            line = self.env['sale.order.line'].browse(result['line_id'])
            line.combo_selection_ids.unlink()
            for item in user_selection:
                self.env['sale.combo.selection'].create({
                    'order_line_id': line.id,
                    'product_id': item.get('product_id'),
                    'quantity': item.get('quantity', 1),
                    'extra_price': item.get('extra_price', 0.0),
                })
           
        return result