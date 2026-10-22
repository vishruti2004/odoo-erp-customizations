from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    kitchen_prep_target_minutes = fields.Float(
        "Kitchen preparation time (min)",
        help="Time to prepare one unit. If empty the PoS category time is used, then the "
             "station default target.")

    def _kitchen_prep_minutes(self):
        self.ensure_one()
        if self.kitchen_prep_target_minutes:
            return self.kitchen_prep_target_minutes
        categories = self.pos_categ_ids.filtered("kitchen_prep_target_minutes").sorted(lambda c: (c.sequence, c.id))
        return categories[:1].kitchen_prep_target_minutes
