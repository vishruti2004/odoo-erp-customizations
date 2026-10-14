# -*- coding: utf-8 -*-

from odoo import api, fields, models

class PosConfig(models.Model):
    _inherit = "pos.config"

    enable_custom_layout = fields.Boolean(
        string="Enable Custom Category Layout",
        default=False,
        help="Customize category layout, appearance, and navigation for this POS.",
    )

    category_layout = fields.Selection(
        [
            ("top_bar", "Top Bar"),
            ("sidebar", "Sidebar"),
            ("popup", "Category Popup"),
        ],
        string="Category Layout",
        default="top_bar",
        required=True,
        help="Display categories in a top bar, sidebar, or popup panel.",
    )

    category_sidebar_position = fields.Selection(
        [
            ("left", "Left"),
            ("right", "Right"),
        ],
        string="Sidebar Position",
        default="left",
        required=True,
        help="Position the category sidebar on the left or right side of the product screen.",
    )

    category_display_style = fields.Selection(
        [
            ("grid", "Grid Cards"),
            ("list", "Nested List"),
        ],
        string="Category Display Style",
        default="grid",
        required=True,
        help="Display sidebar categories as grid cards or a hierarchical nested list.",
    )

    category_card_style = fields.Selection(
        [
            ("classic", "Standard Cards"),
            ("cover", "Cover Image Cards"),
        ],
        string="Card Style",
        default="classic",
        required=True,
        help="Display categories using standard cards or cover image cards.",
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
        help="Display an image, category name, or both on category cards.",
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
        help="Position the category image above, below, or beside the category name.",
    )

    category_scope = fields.Selection(
        [
            ("level", "Direct Subcategories"),
            ("all", "All Nested Categories"),
        ],
        string="Category Visibility",
        default="level",
        required=True,
        help="Display immediate subcategories only or include categories from all nested levels.",
    )

    category_rows = fields.Integer(
        string="Visible Category Rows",
        default=3,
        help="Set the maximum number of visible rows. The layout adjusts to available screen space while preserving room for products.",
    )

    category_carousel = fields.Boolean(
        string="Enable Category Pagination",
        default=False,
        help="Display categories across multiple pages with navigation controls instead of a scrollbar.",
    )

    category_scroll_direction = fields.Selection(
        [
            ("vertical", "Vertical"),
            ("horizontal", "Horizontal"),
        ],
        string="Scroll Direction",
        default="vertical",
        required=True,
        help="Set the scrolling direction for categories in supported layouts.",
    )

    category_popup_scroll_direction = fields.Selection(
        [
            ("horizontal", "Horizontal"),
            ("vertical", "Vertical"),
        ],
        string="Popup Direction",
        default="vertical",
        required=True,
        help="Set the popup orientation and scrolling direction for category navigation.",
    )

    category_sort_order = fields.Selection(
        [
            ("sequence", "Custom Order"),
            ("alphabetical", "Name (A to Z)"),
        ],
        string="Category Sorting",
        default="sequence",
        required=True,
        help="Display categories in their configured sequence or alphabetically by name.",
    )

    category_show_breadcrumb = fields.Boolean(
        string="Show Category Breadcrumb",
        default=True,
        help="Display the navigation path to help users identify their current category level.",
    )

    category_show_product_count = fields.Boolean(
        string="Show Product Count",
        default=False,
        help="Display the number of products associated with each category.",
    )

    category_show_search = fields.Boolean(
        string="Enable Category Search",
        default=False,
        help="Display a search field to find categories by name.",
    )

    category_use_color = fields.Boolean(
        string="Use Category Colors",
        default=False,
        help="Apply configured category colors to supported category elements.",
    )

    category_show_all_popup = fields.Boolean(
        string="Show All Categories Button",
        default=False,
        help="Display a button that opens a searchable window for browsing categories.",
    )

    font_family = fields.Selection(
        selection="_get_available_document_fonts",
        string="Font Family",
        default="Lato",
        required=True,
        help="Set the font family used for category text in the POS interface.",
    )
    @api.model
    def _get_available_document_fonts(self):
            font_field = self.env["base.document.layout"]._fields["font"]
            return font_field._description_selection(self.env)