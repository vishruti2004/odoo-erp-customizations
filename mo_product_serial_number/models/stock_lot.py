from odoo import api, models


class StockLot(models.Model):
    _inherit = 'stock.lot'

    @api.model
    def generate_lot_names(self, first_lot_name, count):
        mo_id = self.env.context.get('default_production_id') or self.env.context.get('active_id')
        if mo_id and self.env.context.get('active_model') == 'mrp.production':
            mo = self.env['mrp.production'].browse(mo_id)
            tmpl = mo.product_id.product_tmpl_id

            if tmpl.use_custom_serial and tmpl.custom_sequence_id:
                seq = tmpl.custom_sequence_id
                
                first_lot_name = seq.get_next_char(seq.number_next_actual)
                
                lots = super().generate_lot_names(first_lot_name, count)
                
                for _ in range(int(count)):
                    seq.next_by_id()
                return lots

        return super().generate_lot_names(first_lot_name, count)