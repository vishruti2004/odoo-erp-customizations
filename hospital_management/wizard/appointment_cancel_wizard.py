from odoo import models, fields
import logging

_logger = logging.getLogger(__name__)

class AppointmentCancelWizard(models.TransientModel):
    _name = 'appointment.cancel.wizard'
    _description = 'Appointment Cancel Wizard'

    appointment_id = fields.Many2one(
        'hospital.appointment',
        required=True
    )

    cancel_reason = fields.Text(
        string="Cancellation Reason",
        required=True
    )

    def action_confirm_cancel(self):

        _logger.warning("========== CANCEL START ==========")

        appointment = self.appointment_id

        appointment.write({
            'cancel_reason': self.cancel_reason,
            'state': 'cancel'
        })

        template = self.env.ref(
            'hospital_management.email_template_appointment_status',
            raise_if_not_found=False
        )

        if not template:
            _logger.error("CANCEL TEMPLATE NOT FOUND")
            # raise ValidationError("Confirm Template Not Found")
            return

        template.send_mail(appointment.id, force_send=True,raise_exception=False)

        # _logger.warning("Cancel Mail Created ID: %s", mail_id)

        # mail_record = self.env['mail.mail'].browse(mail_id)
        # _logger.warning("Cancel Mail State: %s", mail_record.state)
        # _logger.warning("Cancel Email To: %s", mail_record.email_to)

        _logger.warning("========== CANCEL END ==========")

        return {'type': 'ir.actions.act_window_close'}
