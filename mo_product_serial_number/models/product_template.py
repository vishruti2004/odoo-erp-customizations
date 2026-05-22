from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    use_custom_serial = fields.Boolean(string='Use Custom?', default=False)
    custom_serial_prefix = fields.Char(string='Custom Sequence')

    @api.onchange('tracking')
    def _onchange_tracking(self):
        return {}

    def _get_or_create_custom_sequence(self):
        self.ensure_one()
        if not self.use_custom_serial or not self.custom_serial_prefix:
            return False
        sequence = self.env['ir.sequence'].search([
            ('prefix', '=', self.custom_serial_prefix)
        ], limit=1)
        if not sequence:
            sequence = self.env['ir.sequence'].create({
                'name': f'{self.name} Serial Sequence',
                'code': 'stock.lot.serial',
                'prefix': self.custom_serial_prefix,
                'padding': 3,
                'company_id': False,
            })
        return sequence