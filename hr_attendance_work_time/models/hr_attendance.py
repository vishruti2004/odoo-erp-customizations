from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    work_hours_without_break = fields.Float(
        string="Work Hours Without Break",
        compute='_compute_worked_hours',
        store=True,
        widget='float_time',
    )

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        super()._compute_worked_hours()

        for attendance in self:
            attendance.work_hours_without_break = attendance.worked_hours
            resource = attendance.employee_id.resource_id

            if attendance.employee_id.company_id.attendance_work_time_without_break and resource and not resource._is_flexible() and attendance.check_in and attendance.check_out:
                delta = attendance.check_out - attendance.check_in
                attendance.worked_hours = delta.total_seconds() / 3600.0
            else:
                attendance.worked_hours = attendance.worked_hours