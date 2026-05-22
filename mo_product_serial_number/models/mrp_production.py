from odoo import models

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_generate_serial(self):
        self.ensure_one()
        product = self.product_id.product_tmpl_id

        if product.use_custom_serial and product.custom_serial_prefix:
            sequence = product._get_or_create_custom_sequence()
            if sequence:
                product.sudo().lot_sequence_id = sequence

        return super().action_generate_serial()