from odoo import models

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_generate_serial(self):
        self.ensure_one()
        product = self.product_id.product_tmpl_id
        if product.use_custom_serial and product.custom_sequence_id:
            product.sudo().lot_sequence_id = product.custom_sequence_id
        else:
            default_sequence = self.env['ir.sequence'].search([
                ('code', '=', 'stock.lot.serial')
            ], limit=1)
            product.sudo().lot_sequence_id = default_sequence

        return super().action_generate_serial()