from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    def _cron_auto_generate_leaves(self):
        _logger.info("::: Auto Leave Generation Cron Started :::")
        
        target_date = fields.Date.today() - timedelta(days=2)
        employees = self.env['hr.employee'].search([('active', '=', True)])
        leave_type = self.env['hr.leave.type'].search([('name', '=', 'Auto-genrated leave')], limit=1)

        if not leave_type:
            return

        for employee in employees:
            calendar = employee.resource_calendar_id
            if not calendar:
                continue

            is_holiday = calendar.global_leave_ids.filtered(
                lambda l: l.date_from.date() <= target_date <= l.date_to.date()
            )
            if is_holiday:
                continue

            day_index = str(target_date.weekday())
            work_slots = calendar.attendance_ids.filtered(
                lambda l: l.dayofweek == day_index and l.display_type != 'line_section'
            )
            if not work_slots:
                continue

            attendances = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', datetime.combine(target_date, datetime.min.time())),
                ('check_in', '<=', datetime.combine(target_date, datetime.max.time()))
            ])
            
            existing_leaves = self.search([
                ('employee_id', '=', employee.id),
                ('request_date_from', '=', target_date),
                ('state', '!=', 'refuse')
            ])

          
            if not attendances:
                if not existing_leaves.filtered(lambda l: not l.request_unit_half):
                    self.sudo().create({
                        'name': 'Auto-Absent (Full Day)',
                        'employee_id': employee.id,
                        'holiday_status_id': leave_type.id,
                        'request_date_from': target_date,
                        'request_date_to': target_date,
                        'request_unit_half': False,
                        'state': 'confirm',
                    })
                continue 

            for slot in work_slots:
                slot_start = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=slot.hour_from)
                slot_end = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=slot.hour_to)
                
                period = 'am' if slot.day_period == 'morning' else 'pm'

                is_present = attendances.filtered(lambda a: 
                    (a.check_in < slot_end and (a.check_out >= slot_start or not a.check_out))
                )

                if not is_present:
                    already_on_leave = existing_leaves.filtered(
                        lambda l: (l.request_unit_half and l.request_date_from_period == period) or not l.request_unit_half
                    )
                    
                    if not already_on_leave:
                        self.sudo().create({
                            'name': f'Auto-Absent ({period.upper()})',
                            'employee_id': employee.id,
                            'holiday_status_id': leave_type.id,
                            'request_date_from': target_date,
                            'request_date_to': target_date,
                            'request_unit_half': True,
                            'request_date_from_period': period,
                            'request_date_to_period': period,
                            'state': 'confirm',
                        })

        _logger.info("::: Auto Leave Generation Cron Finished :::")