from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"


    def write(self, vals):
        res = super().write(vals)

        if "status_in_payment" in vals:
            paid_invoices = self.filtered(lambda inv: inv.status_in_payment == 'paid')
            
            if paid_invoices:
                appointments = self.env["hospital.appointment"].search([
                    ("invoice_id", "in", paid_invoices.ids)
                ])
                appointments.write({"payment_done": True})

        return res
