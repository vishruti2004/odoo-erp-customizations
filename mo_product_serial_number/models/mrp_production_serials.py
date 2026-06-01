import logging
from odoo import api, models

class MrpProductionSerials(models.TransientModel):
    _inherit = 'mrp.production.serials'

    @api.depends('production_id')
    def _compute_lot_name(self):
        for wizard in self:
            wizard.serial_numbers = '\n'.join(wizard.production_id.lot_producing_ids.mapped('name'))
            if wizard.lot_name:
                continue
            wizard.lot_name = wizard.production_id.lot_producing_ids[:1].name
            if not wizard.lot_name:
                tmpl = wizard.production_id.product_id.product_tmpl_id
                if tmpl.use_custom_serial and tmpl.custom_sequence_id:
                    sequence = tmpl.custom_sequence_id
                else:
                    sequence = self.env['ir.sequence'].search([('code', '=', 'stock.lot.serial')], limit=1)
                wizard.lot_name = sequence.get_next_char(sequence.number_next_actual) if sequence \
                    else wizard.production_id.product_id.serial_prefix_format + wizard.production_id.product_id.next_serial

    def action_generate_serial_numbers(self):
        self.ensure_one()
        tmpl = self.production_id.product_id.product_tmpl_id
        if tmpl.use_custom_serial and tmpl.custom_sequence_id:
            self.lot_name = tmpl.custom_sequence_id.get_next_char(
                tmpl.custom_sequence_id.number_next_actual
            )
        else:
            sequence = self.env['ir.sequence'].search([('code', '=', 'stock.lot.serial')], limit=1)
            if sequence:
                self.lot_name = sequence.get_next_char(sequence.number_next_actual)
        return super().action_generate_serial_numbers()

    def _parse_serial_numbers(self):
        tmpl = self.production_id.product_id.product_tmpl_id
        if tmpl.use_custom_serial and tmpl.custom_sequence_id:
            self.production_id.product_id.sudo().lot_sequence_id = tmpl.custom_sequence_id
        else:
            sequence = self.env['ir.sequence'].search([('code', '=', 'stock.lot.serial')], limit=1)
            if sequence:
                lots = [l.strip() for l in (self.serial_numbers or '').split('\n') if l.strip()]
                sequence.sudo().number_next_actual += len(lots)
        return super()._parse_serial_numbers()