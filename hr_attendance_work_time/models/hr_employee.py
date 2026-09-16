# -*- coding: utf-8 -*-

import pytz
from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.depends(
        'attendance_ids.check_in', 'attendance_ids.check_out', 'attendance_ids.worked_hours',
        'attendance_ids.work_hours_without_break', 'company_id.attendance_work_time_without_break',
    )
    def _compute_hours_today(self):
        now = fields.Datetime.now()
        now_utc = pytz.utc.localize(now)
        for timezone, employees in self.grouped('tz').items():
            tz = pytz.timezone(timezone or 'UTC')
            start_tz = now_utc.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)  # day start in the employee's timezone
            start_naive = start_tz.astimezone(pytz.utc).replace(tzinfo=None)

            attendances_by_employee = dict(self.env['hr.attendance']._read_group(
                [
                    ('employee_id', 'in', employees.ids),
                    ('check_in', '<=', now),
                    '|', ('check_out', '>=', start_naive), ('check_out', '=', False),
                ],
                ['employee_id'],
                ['id:recordset'],
            ))

            for employee in employees:
                attendances = attendances_by_employee.get(employee, self.env['hr.attendance'])
                worked_hours = 0.0
                attendance_worked_hours = 0.0
                for attendance in attendances:
                    if attendance.check_out:
                        if employee.company_id.attendance_work_time_without_break:
                            attendance_worked_hours = attendance.worked_hours or 0.0
                        else:
                            attendance_worked_hours = attendance.work_hours_without_break or 0.0
                    else:
                        # Current running attendance
                        delta = now - max(attendance.check_in, start_naive)
                        attendance_worked_hours = delta.total_seconds() / 3600.0
                    worked_hours += attendance_worked_hours
                employee.last_attendance_worked_hours = attendance_worked_hours
                employee.hours_previously_today = worked_hours - attendance_worked_hours
                employee.hours_today = worked_hours