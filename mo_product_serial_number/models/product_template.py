from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    use_custom_serial = fields.Boolean(string='Use Custom?')
    custom_sequence_id = fields.Many2one('ir.sequence',string='Custom Serial Sequence',domain="[('code', '=', 'product.product'),                ('company_id', '=', company_id)]",)


