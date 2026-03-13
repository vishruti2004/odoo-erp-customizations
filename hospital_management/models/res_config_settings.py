from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    reminder_days = fields.Integer(
        string="Reminder Days",
        default=1
    )

    patient_portal_access_only = fields.Boolean(
        string="Patient Portal access Only"
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    reminder_days = fields.Integer(
        string="Reminder Days",
        related='company_id.reminder_days',
        readonly=False,
    )

    patient_portal_access_only = fields.Boolean(
        string="Patient Portal access  Only",
        related='company_id.patient_portal_access_only',
        readonly=False,
    )