from odoo import models

class PosSession(models.Model):
    _inherit = 'pos.session'

    def _loader_params_pos_order(self):
        result = super()._loader_params_pos_order()
        if 'estimated_delivery_final' not in result['search_params']['fields']:
            result['search_params']['fields'].append('estimated_delivery_final')
        return result