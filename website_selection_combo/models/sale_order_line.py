# -*- coding: utf-8 -*-
from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    combo_selection_ids = fields.One2many(
        "sale.combo.selection",
        "order_line_id",
        string="Combo Selections",
        copy=True,
    )

    is_combo_line = fields.Boolean(
        string="Is Combo Line",
        compute="_compute_is_combo_line",
        store=True,
    )

    @api.depends('combo_selection_ids')
    def _compute_is_combo_line(self):
        for line in self:
            line.is_combo_line = bool(line.combo_selection_ids)

    def get_combo_items(self):
        return [{
            'product_id': sel.product_id.id,
            'product_name': sel.product_id.name,
            'quantity': sel.quantity,
            'extra_price': sel.extra_price,
            'image_url': f'/web/image/product.product/{sel.product_id.id}/image_128',
        } for sel in self.combo_selection_ids]