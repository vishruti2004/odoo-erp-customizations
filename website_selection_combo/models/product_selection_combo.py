# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

class ProductSelectionCombo(models.Model):
    _name = "product.selection.combo"
    _description = "Website Selection Combo"
    _order = "sequence, id"
    _check_company_auto = True

    sequence = fields.Integer(string="Sequence", default=10)
    product_tmpl_id = fields.Many2one("product.template", required=True, ondelete="cascade")
    product_public_category_id = fields.Many2one("product.public.category", required=True)
    selection_method = fields.Selection([
        ("all_products", "All Products"),
        ("selected_products", "Selected Products"),
    ], default="all_products", required=True)
    product_ids = fields.Many2many("product.product", "product_selection_combo_product_rel", "selection_combo_id", "product_id")
    allow_multiple_selection = fields.Boolean()
    minimum_selection = fields.Integer(default=1)
    maximum_selection = fields.Integer(default=1)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)

    @api.constrains("minimum_selection", "maximum_selection")
    def _check_selection_limit(self):
        for record in self:
            if record.minimum_selection < 0 or record.maximum_selection <= 0 or record.minimum_selection > record.maximum_selection:
                raise ValidationError("Invalid min/max selection limits.")

    @api.constrains("selection_method", "product_ids")
    def _check_selected_products(self):
        for record in self:
            if record.selection_method == "selected_products" and not record.product_ids:
                raise ValidationError("Select at least one product for 'Selected Products' mode.")

    @api.onchange("product_public_category_id", "selection_method")
    def _onchange_product_public_category_id(self):
        self.product_ids = [(5, 0, 0)]
        if self.product_public_category_id and self.selection_method == "all_products":
            domain = [("product_tmpl_id.public_categ_ids", "in", [self.product_public_category_id.id])]
            self.product_ids = [(6, 0, self.env["product.product"].search(domain).ids)]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_all_products()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "product_public_category_id" in vals or "selection_method" in vals:
            self._sync_all_products()
        return res

    def _sync_all_products(self):
        for record in self:
            if record.selection_method == "all_products" and record.product_public_category_id:
                domain = [("product_tmpl_id.public_categ_ids", "in", [record.product_public_category_id.id])]
                record.product_ids = [(6, 0, self.env["product.product"].search(domain).ids)]