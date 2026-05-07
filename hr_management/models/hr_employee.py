import logging
from odoo import models, fields
from datetime import timedelta
_logger = logging.getLogger(__name__)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    def _cron_check_attendance_shortfall(self):

        # Access system parameters to fetch configuration values
        config = self.env['ir.config_parameter'].sudo()

        # Get the minimum difference threshold in minutes from settings
        threshold_mins = float(config.get_param('hr_attendance.min_diff_minutes', 0))
        # Convert minutes to decimal hours for calculation
        threshold = threshold_mins / 60.0

        # Set the target date
        date = fields.Date.today() - timedelta(days=2)

        # Retrieve the email template
        template = self.env.ref('hr_management.email_template_timesheet', False)
        if not template:
            _logger.error("Email template 'hr_management.email_template_timesheet' not found!")
            return

        # all active employees 
        for emp in self.search([('active', '=', True), ('work_email', '!=', False)]):

            # Sum total attendance hours for the specific date
            attendance = sum(self.env['hr.attendance'].search([
                ('employee_id', '=', emp.id),
                ('check_in', '>=', f"{date} 00:00:00"),
                ('check_in', '<=', f"{date} 23:59:59"),
            ]).mapped('worked_hours'))

            # Sum total timesheet hours recorded for the same date
            timesheet = sum(self.env['account.analytic.line'].search([
                ('employee_id', '=', emp.id),
                ('date', '=', date),
            ]).mapped('unit_amount'))

            # Calculate the difference between check-in time and timesheet time
            diff = attendance - timesheet
            abs_diff = abs(diff)

            # Check if the absolute difference exceeds the allowed threshold
            if abs_diff >= threshold:
                is_short = diff > 0

                h, m = divmod(round(abs_diff * 60), 60)
                hour_diff_display = ' '.join(filter(None, [f"{h} hr" if h else '', f"{m} min" if m else '']))

                # Send email 
                template.with_context(
                    attendance_hours=round(attendance, 2),
                    timesheet_hours=round(timesheet, 2),
                    hour_diff_display=hour_diff_display,
                    target_date=date,
                    is_short=is_short
                ).send_mail(emp.id, force_send=True, email_values={'email_to': emp.work_email})

                _logger.info("Mail sent to %s for date %s. Diff: %s", emp.name, date, hour_diff_display)