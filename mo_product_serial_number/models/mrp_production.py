from odoo import models

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _prepare_stock_lot_values(self):
        self.ensure_one()
        tmpl = self.product_id.product_tmpl_id
        if tmpl.use_custom_serial and tmpl.custom_sequence_id:
            self.product_id.sudo().lot_sequence_id = tmpl.custom_sequence_id
        else:
            self.product_id.sudo().lot_sequence_id = False
        return super()._prepare_stock_lot_values()