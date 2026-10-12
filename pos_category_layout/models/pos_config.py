# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError

class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_custom_layout = fields.Boolean(
        string="Enable Custom Layout & Configuration",
        default=False,
    )

    category_layout = fields.Selection(
        [
            ("top_bar", "Top Bar"),
            ("sidebar", "Sidebar"),
        ],
        string="Category Layout",
        default="top_bar",
        required=True,
    )

    category_sidebar_position = fields.Selection(
        [
            ("left", "Left"),
            ("right", "Right"),
        ],
        string="Sidebar Position",
        default="left",
        required=True,
    )

    category_display_style = fields.Selection(
        [
            ("grid", "Grid Cards"),
            ("list", "List (Nested Tree)"),
        ],
        string="Category Display Style",
        default="grid",
        required=True,
    )

    category_content = fields.Selection(
        [
            ("image_name", "Image & Name"),
            ("name", "Name Only"),
            ("image", "Image Only"),
        ],
        string="Category Content",
        default="image_name",
        required=True,
    )

    category_show_breadcrumb = fields.Boolean(
        string="Show Category Breadcrumb",
        default=True,
    )

    category_sort_order = fields.Selection(
        [
            ("sequence", "Sequence"),
            ("alphabetical", "Category Name(A to Z)"),
        ],
        string="Category Sorting",
        default="sequence",
        required=True,
    )

    category_show_product_count = fields.Boolean(
        string="Show Product Count",
        default=False,
    )

    category_show_search = fields.Boolean(
        string="Show Category Search Bar",
        default=False,
    )

    product_grid_columns = fields.Integer(
        string="Products Per Row",
        default=4,
        required=True,
    )

    product_sort_order = fields.Selection(
        [
            ("featured", "Featured"),
            ("new_arrivals", "New Arrivals"),
            ("name", "Product Name (A to Z)"),
            ("price_low_high", "Price: Low to High"),
            ("price_high_low", "Price: High to Low"),
        ],
        string="Product Sorting",
        default="featured",
        required=True,
    )

    product_show_price = fields.Boolean(
        string="Show Product Price",
        default=True,
    )

    product_show_description = fields.Boolean(
        string="Show Product Description",
        default=False,
    )

    product_show_list_view = fields.Boolean(
        string="Enable Product List View",
        default=False,
    )

    product_name_bg_color = fields.Char(
        string="Product Background Color",
        default="#FFFFFF",
    )
    @api.model
    def _get_available_document_fonts(self):
        font_field = self.env["base.document.layout"]._fields["font"]
        return font_field._description_selection(self.env)

    font_family = fields.Selection(
        selection="_get_available_document_fonts",
        string="Font Family",
        default="Lato",
        required=True,
    )

    @api.constrains("product_grid_columns")
    def _check_product_grid_columns(self):
        for config in self:
            if not 2 <= config.product_grid_columns <= 12:
                raise ValidationError(
                    self.env._(
                        "Products per row must be between 2 and 12."
                    )
                )