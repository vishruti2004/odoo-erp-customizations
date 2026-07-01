# -*- coding: utf-8 -*-
from odoo import fields, models

class ProductTemplate(models.Model):
    _inherit = "product.template"

    selection_combo = fields.Boolean(
        string="Selection Combo",
        help="Enable website selection combo for this product.",
        tracking=True,
        copy=False,
    )
    selection_combo_line_ids = fields.One2many(
        "product.selection.combo",
        "product_tmpl_id",
        string="Selection Configuration",
        copy=True,
    )