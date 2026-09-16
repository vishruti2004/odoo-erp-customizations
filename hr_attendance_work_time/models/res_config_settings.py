from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_work_time_without_break = fields.Boolean(
        related='company_id.attendance_work_time_without_break',
        readonly=False,
    )