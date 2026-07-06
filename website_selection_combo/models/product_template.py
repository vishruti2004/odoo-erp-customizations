# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    selection_combo = fields.Boolean(tracking=True, copy=False)
    selection_combo_line_ids = fields.One2many("product.selection.combo", "product_tmpl_id", copy=True)
    include_combo_items_price = fields.Boolean(default=True, tracking=True, copy=False)