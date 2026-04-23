from odoo import models, api

class ProductProduct(models.Model):
    _inherit = 'product.product'
    
    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        if 'qty_available' not in fields:
            fields.append('qty_available')
        print(fields)
        return fields
    
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        if 'qty_available' not in fields:
            fields.append('qty_available')
        print(fields)
        return fields
    