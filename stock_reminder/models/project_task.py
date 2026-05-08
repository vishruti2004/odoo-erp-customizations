from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    is_stock_alert_task = fields.Boolean(string="Is Stock Alert Task", default=False)
    alert_product_id = fields.Many2one('product.product', string="Alert Product")

    def action_create_purchase_order(self):
        """Purchase Order form પર redirect કરો - product pre-filled"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Create Purchase Order',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_order_line': [(0, 0, {
                    'product_id': self.alert_product_id.id,
                    'product_qty': 1,
                    'price_unit': self.alert_product_id.standard_price or 0.0,
                })] if self.alert_product_id else [],
            }
        }