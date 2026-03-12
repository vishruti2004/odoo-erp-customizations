from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super().write(vals)

        if 'payment_state' in vals:
            for invoice in self:
                if invoice.payment_state == 'paid':

                    appointments = self.env['hospital.appointment'].search([
                        ('invoice_id', '=', invoice.id)
                    ])

                    appointments.write({
                        'payment_done': True
                    })

        return res