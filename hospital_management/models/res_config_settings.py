from odoo import fields,models



class ResCompany(models.Model):
    _inherit = 'res.company'

    reminder_days = fields.Integer(
        string="Reminder Days",
        default=1
    )        

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    reminder_days = fields.Integer(
        string="Reminder Days",
        related='company_id.reminder_days', 
        readonly=False,
        # config_parameter='hospital.reminder_days' 
    )
