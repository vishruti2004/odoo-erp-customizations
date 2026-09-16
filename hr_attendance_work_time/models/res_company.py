from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_work_time_without_break = fields.Boolean(
        string="Calculate Work Hours Without Break",
        default=True,
    )