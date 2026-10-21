from odoo import fields, models


class PosCategory(models.Model):
    _inherit = "pos.category"

    kitchen_prep_target_minutes = fields.Float(
        "Kitchen preparation time (min)",
        help="Used for every product of the category that has no preparation time of its own.")
