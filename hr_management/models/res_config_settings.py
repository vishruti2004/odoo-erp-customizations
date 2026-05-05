from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_checkin_required = fields.Boolean(
        string='Require Check-in to Access ERP',
        config_parameter='attendance_checkin_restriction.required',
    )

    attendance_checkin_warning_message = fields.Char(
        string='Warning Message',
        config_parameter='attendance_checkin_restriction.warning_message',
    )

    min_diff_minutes = fields.Integer(
        string="Minimum Difference (Minutes)", 
        config_parameter='hr_attendance.min_diff_minutes',
    )