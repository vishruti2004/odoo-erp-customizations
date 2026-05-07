import pytz
from odoo import models, api

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @api.model
    def get_attendance_restriction_info(self):
        
        # Get settings dynamically
        params = self.env['ir.config_parameter'].sudo()
        is_enabled = params.get_param('attendance_checkin_restriction.required') == 'True'
        
        # config time
        late_tolerance = int(params.get_param('attendance_restriction.late_tolerance', 30))

        result = {
            'enabled': is_enabled,
            'checked_in': True,
            'message': params.get_param('attendance_checkin_restriction.warning_message', 'You are late!'),
            'is_late': False,
            'late_minutes': 0
        }

        if not is_enabled:
            return result

        employee = self.env.user.employee_id
        if not employee:
            return result

        # Current check-in status
        result['checked_in'] = employee.attendance_state == 'checked_in'
        last_attendance = employee.last_attendance_id

        if not result['checked_in'] or not last_attendance:
            return result

        calendar = employee.resource_calendar_id
        tz = pytz.timezone(calendar.tz or 'UTC')
        
        # Localize check-in time
        check_in_dt = last_attendance.check_in.astimezone(tz)
        check_in_float = check_in_dt.hour + check_in_dt.minute / 60.0

        # Shifts for today
        daily_shifts = calendar.attendance_ids.filtered(
            lambda s: s.dayofweek == str(check_in_dt.weekday())
        ).sorted('hour_from')

        if not daily_shifts:
            return result

        upcoming_shifts = daily_shifts.filtered(lambda s: s.hour_to > check_in_float)
        if not upcoming_shifts:
            return result

        target_shift = upcoming_shifts[0]
        today_start = last_attendance.check_in.replace(hour=0, minute=0, second=0)

        # Check for duplicate check-ins today to avoid repeating the dialog
        prior_attendance = self.env['hr.attendance'].sudo().search_count([
            ('employee_id', '=', employee.id),
            ('id', '!=', last_attendance.id),
            ('check_in', '>=', today_start),
            ('check_in', '<', last_attendance.check_in),
        ])
        if prior_attendance:
            return result

        has_leave = self.env['hr.leave'].sudo().search_count([
            ('employee_id', '=', employee.id),
            ('state', '!=', 'refuse'),
            ('date_from', '<=', last_attendance.check_in),
            ('date_to', '>=', last_attendance.check_in),
        ])

        # Use current shift start if user was on leave, else use first shift of the day
        reference_start = target_shift.hour_from if has_leave else daily_shifts[0].hour_from
        late_mins = int((check_in_float - reference_start) * 60)

        if late_mins > late_tolerance:
            h, m = divmod(late_mins, 60)
            late_formatted = ' '.join(filter(None, [f"{h} hr" if h else '', f"{m} min" if m else '']))
            result.update({'is_late': True, 'late_minutes': late_mins, 'late_formatted': late_formatted})

        return result