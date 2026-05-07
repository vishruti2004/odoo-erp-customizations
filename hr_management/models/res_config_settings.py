from odoo import models, fields,api
from odoo.exceptions import ValidationError

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

    late_checkin_tolerance = fields.Integer(
        string="Late Check-in Tolerance (Minutes)",
        config_parameter='attendance_restriction.late_tolerance',
    )

    @api.constrains('min_diff_minutes')
    def _check_min_diff_minutes(self):
        for record in self:
            if record.min_diff_minutes < 0:
                raise ValidationError("minutes cannot be negative.enter a value of 0 or more.")