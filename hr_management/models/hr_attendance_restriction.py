import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @api.model
    def get_attendance_restriction_info(self):
        ICP = self.env['ir.config_parameter'].sudo()
        enabled = ICP.get_param('attendance_checkin_restriction.required', 'False') == 'True'
        message = ICP.get_param('attendance_checkin_restriction.warning_message', 'Check-in Required.')

        _logger.info("=== Attendance Restriction Check ===")
        _logger.info(f"User: {self.env.user.name} (ID: {self.env.uid})")
        _logger.info(f"Restriction Enabled in Settings: {enabled}")

        if not enabled or self.env.is_admin():
            _logger.info("Access Bypass: Restriction is disabled or User is Admin.")
            return {'enabled': False, 'checked_in': True, 'message': ''}

        employee = self.env.user.employee_id
        if not employee:
            _logger.warning(f"No employee linked to User {self.env.user.name}. Bypassing.")
            return {'enabled': enabled, 'checked_in': True, 'message': ''}

        is_checked_in = employee.attendance_state == "checked_in"
        _logger.info(f"Employee: {employee.name} | Current State: {employee.attendance_state}")
        _logger.info(f"Result: {'Access Blocked' if not is_checked_in else 'Access OK'}")

        return {
            'enabled': True,
            'checked_in': is_checked_in,
            'message': message,
        }