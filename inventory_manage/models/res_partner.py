from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    total_sp_commission = fields.Monetary(
        string="Total Sales Commission",
        compute="_compute_total_sp_commission",
        currency_field='currency_id',
    )

   

    def _compute_total_sp_commission(self):
        for partner in self:
            total_converted = 0.0

            user = self.env['res.users'].search([('partner_id', '=', partner.id)], limit=1)
            
            if user:
                orders = self.env['sale.order'].search([
                    ('user_id', '=', user.id),
                    ('state', 'in', ['sale', 'done'])
                ])
                
                for order in orders:
                    if order.currency_id != partner.currency_id:
                        converted = order.currency_id._convert(
                            order.total_sp_commission, 
                            partner.currency_id,      
                            order.company_id,        
                            order.date_order or fields.Date.today()
                        )
                    else:
                        converted = order.total_sp_commission

                    total_converted += converted
            
            partner.total_sp_commission = total_converted