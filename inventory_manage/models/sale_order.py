from odoo import models, fields, api  # ← આ line ઉમેર

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    total_sp_commission = fields.Monetary(
        string="Sale Person Commission",
        compute="_compute_total_sp_commission",
        store=True,
        currency_field='currency_id',
    )

    @api.depends('order_line.sp_commission_amount')
    def _compute_total_sp_commission(self):
        for order in self:
            order.total_sp_commission = sum(
                order.order_line.mapped('sp_commission_amount')
            )