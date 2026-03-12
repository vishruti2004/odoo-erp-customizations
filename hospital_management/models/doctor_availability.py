from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HospitalDoctorAvailability(models.Model):
    _name = 'hospital.doctor.availability'
    _description = 'Doctor Availability'
    _order = 'available_datetime_from'

    doctor_id = fields.Many2one(
        'hospital.doctor',
        ondelete='cascade',
        required=True
    )

    available_datetime_from = fields.Datetime(
        string="From",
        required=True
    )

    available_datetime_to = fields.Datetime(
        string="To",
        required=True
    )

    
    # Auto copy date from to "to"

    @api.onchange('available_datetime_from')
    def _onchange_from(self):
        for rec in self:
            if rec.available_datetime_from and not rec.available_datetime_to:
                rec.available_datetime_to = rec.available_datetime_from

    # Validation

    @api.constrains('available_datetime_from', 'available_datetime_to')
    def _check_validations(self):
        for rec in self:

            # No past datetime
            if rec.available_datetime_from < fields.Datetime.now():
                raise ValidationError(
                    "Cannot set availability in the past."
                )

            # To must be greater than From
            if rec.available_datetime_from >= rec.available_datetime_to:
                raise ValidationError(
                    "End datetime must be greater than start datetime."
                )

            # Sunday block
            if rec.available_datetime_from.weekday() == 6:
                raise ValidationError(
                    "Doctor cannot be available on Sunday."
                )
            


            # Public Holiday block (Time Off module)
            holiday = self.env['resource.calendar.leaves'].search([
                ('date_from', '<=', rec.available_datetime_from),
                ('date_to', '>=', rec.available_datetime_from),
                ('company_id', '=', self.env.company.id),
            ], limit=1)

            if holiday:
                raise ValidationError(
                    "Cannot set availability on Public Holiday."
                )


            # Overlapping availability
            domain = [
                ('id', '!=', rec.id),
                ('doctor_id', '=', rec.doctor_id.id),
                ('available_datetime_from', '<', rec.available_datetime_to),
                ('available_datetime_to', '>', rec.available_datetime_from),
            ]

            overlap = self.search(domain, limit=1)

            if overlap:
                raise ValidationError(
                    "This availability overlaps with existing entry."
                )



