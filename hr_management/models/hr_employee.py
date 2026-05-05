from odoo import models, fields
from datetime import timedelta


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _cron_check_attendance_shortfall(self):
        config = self.env['ir.config_parameter']
        threshold = float(config.get_param('hr_attendance.min_diff_minutes', 0)) / 60.0
        date = fields.Date.today() - timedelta(days=1)

        template = self.env.ref('hr_management.email_template_timesheet', False)
        if not template:
            return

        for emp in self.search([('active', '=', True), ('work_email', '!=', False)]):

            attendance = sum(self.env['hr.attendance'].search([
                ('employee_id', '=', emp.id),
                ('check_in', '>=', f"{date} 00:00:00"),
                ('check_in', '<=', f"{date} 23:59:59"),
            ]).mapped('worked_hours'))

            timesheet = sum(self.env['account.analytic.line'].search([
                ('employee_id', '=', emp.id),
                ('date', '=', date),
            ]).mapped('unit_amount'))

            diff = attendance - timesheet

            if diff >= threshold:
                template.with_context(
                    attendance_hours=round(attendance, 2),
                    timesheet_hours=round(timesheet, 2),
                    minute_difference=round(diff * 60),
                    target_date=date
                ).send_mail(emp.id, force_send=True,
                            email_values={'email_to': emp.work_email})