from odoo import models, fields, api
from datetime import timedelta

class PosOrder(models.Model):
    _inherit = 'pos.order'

    estimated_delivery_final = fields.Datetime(
        string="Estimated Delivery", 
        compute="_compute_estimated_delivery",
        store=True
    )

    delivery_boy_id = fields.Many2one('res.users', string='Delivery Boy')

    

    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        res['delivery_boy_id'] = ui_order.get('delivery_boy_id', False)
        return res

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


   