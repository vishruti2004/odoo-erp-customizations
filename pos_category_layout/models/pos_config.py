from odoo import api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    # Category layout
    category_layout = fields.Selection(
        [
            ("top_bar", "Top Bar Display"),
            ("horizontal", "Horizontal Category Layout"),
            ("sidebar", "Sidebar Display"),
        ],
        string="Category Layout",
        default="top_bar",
        required=True,
    )
    category_sidebar_position = fields.Selection(
        [("left", "Left"), ("right", "Right")],
        string="Category Sidebar Position",
        default="left",
        required=True,
    )
    category_sort_order = fields.Selection(
        [("sequence", "Sequence"), ("alphabetical", "Alphabetical")],
        string="Category Sorting",
        default="alphabetical",
        required=True,
    )

    # Product display
    product_card_style = fields.Selection(
        [
            ("standard", "Standard"),
            ("compact", "Compact"),
            ("image_focused", "Image-Focused"),
        ],
        string="Product Card Design",
        default="standard",
        required=True,
    )
    product_grid_columns = fields.Integer(string="Product Grid Columns", default=4)
    product_card_spacing = fields.Selection(
        [("compact", "Compact"), ("normal", "Normal"), ("spacious", "Spacious")],
        string="Product Card Spacing",
        default="normal",
        required=True,
    )

    # Colors
    primary_color = fields.Char(string="Primary Color", default="#8CC187")
    category_color = fields.Char(string="Category Color", default="#FFFFFF")
    product_color = fields.Char(string="Product Card Color", default="#FFFFFF")

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
            if not 1 <= config.product_grid_columns <= 12:
                raise ValidationError(self.env._("Product grid columns must be between 1 and 12."))
