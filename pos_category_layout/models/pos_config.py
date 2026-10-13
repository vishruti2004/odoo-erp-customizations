# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_custom_layout = fields.Boolean(
        string="Enable Custom Category Layout",
        default=False,
    )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    category_layout = fields.Selection(
        [
            ("top_bar", "Top Bar"),
            ("sidebar", "Sidebar"),
            ("popup", "Popup (Icon Only)"),
        ],
        string="Category Layout",
        default="top_bar",
        required=True,
        help="Popup: the product screen keeps the full page, categories open from "
        "an icon in a popup.",
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

    category_card_style = fields.Selection(
        [
            ("classic", "Normal Cards"),
            ("cover", "Cover Image Cards"),
        ],
        string="Card Style",
        default="classic",
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

    category_image_position = fields.Selection(
        [
            ("top", "Top"),
            ("bottom", "Bottom"),
            ("left", "Left"),
            ("right", "Right"),
        ],
        string="Image Position",
        default="left",
        required=True,
    )

    category_grid_columns = fields.Integer(
        string="Categories Per Row",
        default=0,
        help="0 = automatic (as many as fit). Applies to the top bar and to the categories popup.",
    )

    category_rows = fields.Integer(
        string="Visible Category Rows",
        default=3,
        help="Rows shown before scrolling (or before the next page). Applies to the top bar "
        "and to the categories popup.",
    )

    category_carousel = fields.Boolean(
        string="Pagination Instead of Scrollbar",
        default=False,
        help="Show the categories page by page (arrows and swipe) instead of a "
        "scrollbar. Applies to the top bar and to the categories popup.",
    )

    category_scroll_direction = fields.Selection(
        [
            ("vertical", "Vertical"),
            ("horizontal", "Horizontal"),
        ],
        string="Scrollbar Direction",
        default="vertical",
        required=True,
        help="Vertical: rows scroll up / down. Horizontal: the visible rows scroll left / right. "
        "Applies to the top bar and to the categories popup.",
    )
    # ------------------------------------------------------------------
    # Display options
    # ------------------------------------------------------------------
    category_sort_order = fields.Selection(
        [
            ("sequence", "Sequence"),
            ("alphabetical", "Category Name(A to Z)"),
        ],
        string="Category Sorting",
        default="sequence",
        required=True,
    )

    category_show_breadcrumb = fields.Boolean(
        string="Show Category Breadcrumb",
        default=True,
    )

    category_show_product_count = fields.Boolean(
        string="Show Product Count",
        default=False,
    )

    category_show_search = fields.Boolean(
        string="Show Category Search Bar",
        default=False,
    )

    category_use_color = fields.Boolean(
        string="Use Category Colors",
        default=False,
        help="Show the category color on parent and sub categories. "
        "Categories without any parent or child stay white.",
    )

    category_show_all_popup = fields.Boolean(
        string="Show 'All Categories' Button",
        default=False,
        help="Adds a button that opens a popup with the categories shown in the "
        "category view, with a search bar. Click the button again to close it.",
    )

    # ------------------------------------------------------------------
    # Typography (categories only)
    # ------------------------------------------------------------------
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

    @api.constrains("category_grid_columns", "category_rows")
    def _check_category_grid(self):
        for config in self:
            if not 0 <= config.category_grid_columns <= 12:
                raise ValidationError(
                    self.env._("Categories per row must be between 0 (auto) and 12.")
                )
            if not 1 <= config.category_rows <= 8:
                raise ValidationError(
                    self.env._("Visible category rows must be between 1 and 8.")
                )