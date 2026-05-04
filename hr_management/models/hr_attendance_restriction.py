from odoo import models, api

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @api.model
    def get_attendance_restriction_info(self):
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('attendance_checkin_restriction.required') == 'True'
        
        if enabled:
            employee = self.env.user.employee_id
            msg = ICP.get_param('attendance_checkin_restriction.warning_message', 'Check-in Required.')
            
            if employee:
                is_checked_in = employee.attendance_state == "checked_in"
                return {'enabled': True, 'checked_in': is_checked_in, 'message': msg}
            else:
                return {'enabled': True, 'checked_in': False, 'message': "No employee profile linked. Access denied."}

        return {'enabled': False, 'checked_in': True, 'message': ''}