from odoo import models, fields, api
from datetime import timedelta

class PosOrder(models.Model):
    _inherit = 'pos.order'

    estimated_delivery_final = fields.Datetime(
        string="Estimated Delivery", 
        compute="_compute_estimated_delivery",
        store=True
    )

    @api.depends('date_order', 'session_id.config_id.delivery_type', 
                 'session_id.config_id.estimated_delivery_date')
    def _compute_estimated_delivery(self):
        for order in self:
            config = order.session_id.config_id
            if order.date_order and config and config.estimated_delivery_date:
                duration = config.estimated_delivery_date
                if config.delivery_type == 'hours':
                    order.estimated_delivery_final = order.date_order + timedelta(hours=duration)
                else:
                    order.estimated_delivery_final = order.date_order + timedelta(days=duration)
            else:
                order.estimated_delivery_final = False
                
    def _loader_params_pos_order(self):
        result = super()._loader_params_pos_order()
        result['search_params']['fields'].append('estimated_delivery_final')
        return result