from odoo import models, fields

class ProductProduct(models.Model):
    _inherit = 'product.product'

    use_custom_serial = fields.Boolean(related='product_tmpl_id.use_custom_serial',readonly=False,)
    custom_sequence_id = fields.Many2one(related='product_tmpl_id.custom_sequence_id', readonly=False,)