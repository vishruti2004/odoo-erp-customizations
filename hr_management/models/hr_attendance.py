import pytz
from odoo import models
from datetime import datetime, time

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    def _dt_to_float(self, dt, tz):
        local_dt = dt.replace(tzinfo=pytz.utc).astimezone(tz)
        return local_dt, local_dt.hour + local_dt.minute / 60.0

    def _cron_auto_check_out_by_schedule(self):

        # Fetch all attendance records that not checked out yet
        active_attendances = self.search([('check_out', '=', False)])

        for attendance in active_attendances:
            employee = attendance.employee_id
            calendar = employee.resource_calendar_id

            # Skip if no working calendar is assigned to the employee
            if not calendar:
                continue

            # Identify employee's local timezone for accurate time conversion
            user_tz = pytz.timezone(calendar.tz or 'UTC')
            localized_check_in, check_in_float = self._dt_to_float(attendance.check_in, user_tz)

            # check leave
            active_leave = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('state', '!=', 'refuse'),
                ('request_date_from', '<=', localized_check_in.date()),
                ('request_date_to', '>=', localized_check_in.date()),
            ], limit=1)

            target_checkout_time = 0.0

            # Leave handling
            if active_leave:
                _, leave_start_float = self._dt_to_float(active_leave.date_from, user_tz)

                # If check-in happened before the leave start time (half-day leave)
                if check_in_float < leave_start_float:
                    target_checkout_time = leave_start_float

            # If no leave or check-in happened during leave (use working schedule)
            if not target_checkout_time:
                day_index = str(localized_check_in.weekday())
                daily_schedule = calendar.attendance_ids.filtered(lambda l: l.dayofweek == day_index)

                if daily_schedule:
                    # Find the nearest slot end time after the check-in time, else use day's max
                    upcoming_slots = daily_schedule.filtered(lambda l: l.hour_to > check_in_float)
                    target_checkout_time = min(upcoming_slots.mapped('hour_to')) if upcoming_slots else max(daily_schedule.mapped('hour_to'))

            # Apply the checkout time in UTC format
            if target_checkout_time:
                hour = int(target_checkout_time)
                minute = int(round((target_checkout_time - hour) * 60))

                # Combine original check-in date with the calculated checkout time
                final_local_dt = user_tz.localize(datetime.combine(localized_check_in.date(), time(hour, minute)))

                # Write to the database by converting back to UTC (standard Odoo format)
                attendance.sudo().write({
                    'check_out': final_local_dt.astimezone(pytz.utc).replace(tzinfo=None)
                })