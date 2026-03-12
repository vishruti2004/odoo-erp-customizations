from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
from datetime import date

_logger = logging.getLogger(__name__)

class HospitalDoctor(models.Model):
    _name = 'hospital.doctor'
    _description = 'Doctor'
    _rec_name = 'display_name'
    _order = 'active desc, id desc'   # Active doctors first
    _inherit = ['mail.thread', 'mail.activity.mixin']


    partner_id = fields.Many2one(
        'res.partner',
        string="Doctor",
        required=True,
        ondelete='cascade'
    )

    user_id = fields.Many2one(
        'res.users',
        string="User",
        readonly=True
    )

    name = fields.Char(related='partner_id.name', store=True,tracking=True)
    email = fields.Char(related='partner_id.email', store=True,tracking=True)
    phone = fields.Char(related='partner_id.phone', store=True,tracking=True)

    doctor_code = fields.Char(
        string="Doctor ID",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True
    )

    date_of_birth = fields.Date(string="Date of Birth",tracking=True)

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        default=lambda self: self.env.company,
        tracking=True
    )

    active = fields.Boolean("Active", default=True,tracking=True)

    specialization_id = fields.Many2one(
        'hospital.specialization',
        string="Specialization",
        required=True,
        tracking=True
    )

    resource_calendar_id = fields.Many2one(
        'resource.calendar',
        string="Working Schedule",
        required=True,
        tracking=True
    )

    # consultation_fee = fields.Float(string="Consultation Fee",tracking=True)

    consultation_fee = fields.Monetary(
    string="Consultation Fee",
    currency_field='currency_id',
    tracking=True
    )

    currency_id = fields.Many2one(
    'res.currency',
    default=lambda self: self.env.company.currency_id
)

    slot_duration = fields.Integer(
        string="Slot Duration (Minutes)",
        default=15,
        required=True,
        tracking=True
    )

   
    #  One2many relation 
    appointment_ids = fields.One2many(
        'hospital.appointment',
        'doctor_id',
        string="Appointments"
    )

    #  Appointment Count
    appointment_count = fields.Integer(
        string="Appointment Count",
        compute="_compute_appointment_count"
    )

    is_editable = fields.Boolean(compute='_compute_is_editable', store=False)

    @api.depends('user_id')
    def _compute_is_editable(self):
        is_admin = self.env.user.has_group('hospital_management.group_admin')
        for rec in self:
            if is_admin or (rec.user_id.id == self.env.user.id):
                rec.is_editable = True
            else:
                rec.is_editable = False

    # appoitment count logic

    def _compute_appointment_count(self):
        for record in self:
            record.appointment_count = self.env['hospital.appointment'].search_count([
                ('doctor_id', '=', record.id)
            ])

    #smart button logic

    def action_open_appointments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Appointments',
            'view_mode': 'list,form',
            'res_model': 'hospital.appointment',
            'domain': [('doctor_id', '=', self.id)],
            'context': {'default_doctor_id': self.id,
                         'default_specialization_id': self.specialization_id.id},
        }


    @api.depends('doctor_code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.doctor_code or ''}] {rec.name or ''}"


   
    #sequence code doctor

    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('doctor_code', 'New') == 'New':
    #             vals['doctor_code'] = self.env['ir.sequence'].next_by_code(
    #                 'hospital.doctor'
    #             ) or 'New'

    #     records = super().create(vals_list)

    #     for rec in records:
    #         group_user = self.env.ref('base.group_user')
    #         group_doctor = self.env.ref('hospital_management.group_doctor')

    #         user = self.env['res.users'].sudo().with_context(
    #             no_reset_password=True
    #         ).create({
    #             'name': rec.name,
    #             'login': rec.doctor_code,
    #             # 'password': 'doctor123',
    #             'partner_id': rec.partner_id.id,
    #             'group_ids': [(6, 0, [group_user.id, group_doctor.id])],
    #         })
    #         rec.user_id = user.id

    #     return records


    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            if vals.get('doctor_code', 'New') == 'New':
                vals['doctor_code'] = self.env['ir.sequence'].next_by_code(
                    'hospital.doctor'
                ) or 'New'

        records = super().create(vals_list)

        for rec in records:

            group_user = self.env.ref('base.group_user')
            group_doctor = self.env.ref('hospital_management.group_doctor')

            # CHECK USER EXIST OR NOT
            existing_user = self.env['res.users'].sudo().search([
                ('partner_id', '=', rec.partner_id.id)
            ], limit=1)

            if existing_user:
                rec.user_id = existing_user.id

            else:
                user = self.env['res.users'].sudo().create({
                    'name': rec.name,
                    'login': rec.email,
                    'partner_id': rec.partner_id.id,
                    'group_ids': [(6, 0, [group_user.id, group_doctor.id])],
                })

                rec.user_id = user.id

                # SEND PASSWORD SETUP MAIL
                user.action_reset_password()

        return records

    #birthday mail logic

    def action_send_doctor_birthday_mail(self):

        today = date.today()
        _logger.info("Birthday Cron Started for date: %s", today)

        all_active_doctors = self.search([
            ('active', '=', True),
            ('date_of_birth', '!=', False),
            ('email', '!=', False)
        ])

        birthday_doctors = all_active_doctors.filtered(
            lambda d: d.date_of_birth.month == today.month and
                      d.date_of_birth.day == today.day
        )

        if not birthday_doctors:
            _logger.info("No doctor birthdays found today.")
            return

        wish_template = self.env.ref(
            'hospital_management.email_template_doctor_birthday_wish',
            raise_if_not_found=False
        )
        notif_template = self.env.ref(
            'hospital_management.email_template_doctor_birthday_notification',
            raise_if_not_found=False
        )

        if not wish_template or not notif_template:
            _logger.error("Birthday templates not found! Please check XML IDs.")
            return

        for b_doctor in birthday_doctors:

            # Send birthday wish
            wish_template.send_mail(b_doctor.id, force_send=True)
            _logger.info("Birthday wish sent to: %s", b_doctor.name)

            # Notify other doctors
            other_doctors = all_active_doctors.filtered_domain([
                ('id', '!=', b_doctor.id)
            ])

            partner_ids = other_doctors.mapped('partner_id').ids

            if partner_ids:
                notif_template.send_mail(
                    b_doctor.id,
                    force_send=True,
                    email_values={
                        'recipient_ids': [(6, 0, partner_ids)]
                    }
                )

            _logger.info(
                "Birthday notification for %s sent to %s doctors",
                b_doctor.name,
                len(other_doctors)
            )