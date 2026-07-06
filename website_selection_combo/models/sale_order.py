from odoo import models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.model
    def _cart_add(self, **kwargs):
        user_selection = kwargs.pop('user_selection', None)
        result = super()._cart_add(**kwargs)

        if user_selection and result.get('line_id'):
            line = self.env['sale.order.line'].browse(result['line_id'])
            line.combo_selection_ids.unlink()
            for item in user_selection:
                self.env['sale.combo.selection'].create({
                    'order_line_id': line.id,
                    'product_id': item['product_id'],
                    'quantity': item.get('quantity', 1),
                    'extra_price': item.get('extra_price', 0),
                })
            line._update_combo_name()
        return result