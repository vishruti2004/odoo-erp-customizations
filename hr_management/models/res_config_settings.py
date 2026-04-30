from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_checkin_required = fields.Boolean(
        string='Require Check-in to Access ERP',
        config_parameter='attendance_checkin_restriction.required',
    )

    attendance_checkin_warning_message = fields.Char(
        string='Warning Message',
        config_parameter='attendance_checkin_restriction.warning_message',
        default='We have noticed that you have not completed your check-in process.\n'
                'To ensure access to the system, please perform the check-in at your '
                'earliest convenience. Access to the ERP will be restricted until '
                'this step is completed.'
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        msg = ICP.get_param('attendance_checkin_restriction.warning_message', '')
        res['attendance_checkin_warning_message'] = msg
        return res

    def set_values(self):
        super().set_values()
        self.env['ir.config_parameter'].sudo().set_param(
            'attendance_checkin_restriction.warning_message',
            self.attendance_checkin_warning_message or ''
        )

    