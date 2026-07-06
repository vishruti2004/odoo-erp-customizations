# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleComboSelection(models.Model):
    _name = "sale.combo.selection"
    _description = "Combo Selection"
    _rec_name = "product_id"

    order_line_id = fields.Many2one("sale.order.line", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", required=True)
    quantity = fields.Float(default=1.0, required=True)
    extra_price = fields.Float(default=0.0)