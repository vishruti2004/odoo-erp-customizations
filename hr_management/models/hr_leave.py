from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    #  define how many days in advance a leave must be applied
    min_notice_days = fields.Integer(
        string="Notice Days",
        default=0,
    )
class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def _create_auto_absent(self, employee, leave_type, target_date, is_half=False, period=None):
        name = f'Auto-Absent ({period.upper()})' if is_half else 'Auto-Absent (Full Day)'
        vals = {
            'name': name,
            'employee_id': employee.id,
            'holiday_status_id': leave_type.id,
            'request_date_from': target_date,
            'request_date_to': target_date,
            'request_unit_half': is_half,
            'state': 'confirm',
        }
        if is_half and period:
            vals.update({'request_date_from_period': period, 'request_date_to_period': period})
        self.sudo().create(vals)

    def _cron_auto_generate_leaves(self):

        _logger.info("::: Auto Leave Generation Cron Started :::")

        # Target date is set to today for processing
        target_date = fields.Date.today() + timedelta(days=3)

        # Fetch all active employees
        employees = self.env['hr.employee'].search([('active', '=', True)])

        # Look for the specific leave type used for auto-generation
        leave_type = self.env['hr.leave.type'].search([('name', '=', 'Auto-genrated leave')], limit=1)
        if not leave_type:
            _logger.error("Leave type 'Auto-genrated leave' not found!")
            return

        for employee in employees:
            # Check if employee has a working schedule assigned
            calendar = employee.resource_calendar_id
            if not calendar:
                continue

            # Skip if the target date is a public/global holiday
            is_holiday = calendar.global_leave_ids.filtered(
                lambda l: l.date_from.date() <= target_date <= l.date_to.date()
            )
            if is_holiday:
                continue

            # Identify if the target date is a working day for this employee
            day_index = str(target_date.weekday())
            work_slots = calendar.attendance_ids.filtered(
                lambda l: l.dayofweek == day_index and l.display_type != 'line_section'
            )
            if not work_slots:
                continue

            day_start = datetime.combine(target_date, datetime.min.time())

            # Check if any attendance record exists for the target date
            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', day_start),
                ('check_in', '<=', datetime.combine(target_date, datetime.max.time()))
            ])

            # Check if there's already an approved or confirmed leave for that day
            existing_leaves = self.search([
                ('employee_id', '=', employee.id),
                ('request_date_from', '=', target_date),
                ('state', '!=', 'refuse')
            ])

            # FULL DAY Absence
            if not attendances:
                # If no attendance and no full-day leave exists, create an Auto-Absent record
                if not existing_leaves.filtered(lambda l: not l.request_unit_half):
                    self._create_auto_absent(employee, leave_type, target_date)
                continue

            # HALF DAY Absence (Morning/Afternoon shifts)
            for slot in work_slots:
                slot_start = day_start + timedelta(hours=slot.hour_from)
                slot_end = day_start + timedelta(hours=slot.hour_to)

                period = 'am' if slot.day_period == 'morning' else 'pm'

                # Check if employee was present during this specific shift slot
                is_present = attendances.filtered(
                    lambda a: a.check_in < slot_end and (a.check_out >= slot_start or not a.check_out)
                )

                if not is_present:
                    # If absent during shift, check if they already applied for half-day leave
                    already_on_leave = existing_leaves.filtered(
                        lambda l: (l.request_unit_half and l.request_date_from_period == period) or not l.request_unit_half
                    )
                    if not already_on_leave:
                        # Create Half-Day Auto-Absent record
                        self._create_auto_absent(employee, leave_type, target_date, is_half=True, period=period)

        _logger.info("::: Auto Leave Generation Cron Finished :::")

    @api.constrains('date_from')
    def _check_minimum_notice_period(self):

        # Check if the current user is an Admin or Manager
        is_privileged_user = (
            self.env.user.has_group('hr_holidays.group_hr_holidays_manager') or
            self.env.user.has_group('base.group_system')
        )

        for leave in self:
            # Skip validation for Auto-generated leaves or privileged users
            if leave.holiday_status_id.name == 'Auto-genrated leave' or is_privileged_user:
                continue

            min_days = leave.holiday_status_id.min_notice_days
            if min_days and leave.date_from:
                # Calculate the minimum allowed date for leave application
                min_date = fields.Datetime.now() + timedelta(days=min_days)

                # Raise error if leave is applied too late
                if leave.date_from < min_date:
                    raise ValidationError(f"Leave must be applied at least {min_days} days before.")