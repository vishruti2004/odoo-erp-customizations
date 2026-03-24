from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)



class HospitalAppointment(models.Model):
    _name = "hospital.appointment"
    _description = "Hospital Appointment"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "start_datetime desc"

    # FIELDS

    name = fields.Char(
        string="Appointment ID",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )

    specialization_id = fields.Many2one(
        "hospital.specialization", required=True, tracking=True
    )

    doctor_id = fields.Many2one(
        "hospital.doctor",
        # domain="[('specialization_id', '=', specialization_id)]",.
        domain = [],
        required=True,
        tracking=True,
    )

    patient_id = fields.Many2one("hospital.patient", required=True, tracking=True)

    start_datetime = fields.Datetime(required=True, tracking=True)

    end_datetime = fields.Datetime(
        compute="_compute_end_datetime", store=True, readonly=True, tracking=True
    )

    description = fields.Text(tracking=True)

   

    consultation_fee = fields.Monetary(
        related="doctor_id.consultation_fee",
        currency_field="currency_id",
        store=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, readonly=True
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    reminder_sent = fields.Boolean(default=False)

    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True)

    payment_done = fields.Boolean(
        string="Payment Done",
        compute="_compute_payment_done",
        store=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("request", "Requested"),
            ("confirm", "Confirmed"),
            ("consult", "In Consultation"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )

    active = fields.Boolean(default=True, tracking=True)

    cancel_reason = fields.Text()
    doc_description = fields.Text()

    color = fields.Integer(compute="_compute_color", store=True)

    # website_url = fields.Char(
    # compute="_compute_website_url"
    # )

    # def _compute_website_url(self):
    #     for rec in self:
    #         rec.website_url = "/my/appointment/%s" % rec.id

    # invoice_ids = fields.One2many(
    #     "account.move",
    #     "invoice_origin",
    #     string="Invoices",
    # )

    invoice_total = fields.Monetary(
        string="Invoiced",
        compute="_compute_invoice_total",
        currency_field="currency_id",
    )

    def _compute_invoice_total(self):
        for rec in self:
            invoices = self.env["account.move"].search(
                [
                    ("invoice_origin", "=", rec.name),
                    ("move_type", "=", "out_invoice"),
                    ("state", "=", "posted"),
                ]
            )
            rec.invoice_total = sum(invoices.mapped("amount_total"))

    def action_open_invoices(self):
        self.ensure_one()
        
        return {
            "type": "ir.actions.act_window",
            "name": "Invoices",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [
                ("invoice_origin", "=", self.name), 
                ("move_type", "=", "out_invoice")
            ],
            "context": "{'default_move_type': 'out_invoice'}", # Optional: Navi invoice banave to direct 'Customer Invoice' bane
        }
    
    is_doctor = fields.Boolean(compute="_compute_visibility")
    is_patient = fields.Boolean(compute="_compute_visibility")

    @api.depends("invoice_id", "invoice_id.payment_state")
    def _compute_payment_done(self):
        for rec in self:
            if rec.invoice_id and rec.invoice_id.payment_state == "paid":
                rec.payment_done = True
            else:
                rec.payment_done = False

            _logger.debug("PAYMENT STATE: %s", rec.invoice_id.payment_state)

    @api.depends("doctor_id", "patient_id")
    def _compute_visibility(self):
        # Admin group check
        is_admin = self.env.user.has_group("hospital_management.group_admin")
        for rec in self:
            # Doctor check: 
            is_assigned_doc = rec.doctor_id.user_id.id == self.env.user.id
            rec.is_doctor = is_admin or is_assigned_doc

            # Patient check:
            rec.is_patient = rec.patient_id.user_id.id == self.env.user.id

    # --- Cancel Buttons Logic ---

    def action_cancel(self):
        return {
            "name": "Cancel Appointment",
            "type": "ir.actions.act_window",
            "res_model": "appointment.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_appointment_id": self.id},
        }

    def action_patient_cancel(self):
        for rec in self:
            rec.state = "cancel"
            rec.message_post(body=_("Appointment cancelled by Patient."))

    def _get_report_base_filename(self):
        self.ensure_one()
        return f"Appointment_{self.name}"

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = "/my/appointment/%s" % rec.id

    # COMPUTE METHODS

    @api.depends("state")
    def _compute_color(self):
        color_map = {
            "draft": 0,
            "request": 4,
            "confirm": 10,
            "consult": 3,
            "done": 5,
            "cancel": 1,
        }
        for rec in self:
            rec.color = color_map.get(rec.state, 0)

    @api.depends("start_datetime", "doctor_id")
    def _compute_end_datetime(self):
        for rec in self:
            if rec.start_datetime and rec.doctor_id:
                slot = rec.doctor_id.slot_duration or 15
                rec.end_datetime = rec.start_datetime + timedelta(minutes=slot)
            else:
                rec.end_datetime = False

    # CREATE

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("hospital.appointment")
                    or "New"
                )
        return super().create(vals_list)

    # automatic show specialization and name

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        doctor = self.env["hospital.doctor"].search(
            [("user_id", "=", self.env.user.id)], limit=1
        )

        _logger.debug("LOGIN USER: %s", self.env.user.name)
        _logger.debug("DOCTOR FOUND: %s", doctor)

        if doctor:
            res["doctor_id"] = doctor.id
            res["specialization_id"] = doctor.specialization_id.id

        patient = self.env["hospital.patient"].search(
            [("user_id", "=", self.env.user.id)], limit=1
        )

        _logger.debug("LOGIN USER: %s", self.env.user.name)
        _logger.debug("PATIENT FOUND: %s", patient)
        if patient:
            res["patient_id"] = patient.id


        return res



    @api.constrains("start_datetime",  "end_datetime","doctor_id", "patient_id")
    def _check_appointment_rules(self):

        for rec in self:

            if not rec.start_datetime and rec.end_datetime:
                continue

            for rec in self:
                if rec.start_datetime and rec.end_datetime and rec.start_datetime.date() != rec.end_datetime.date():
                    raise ValidationError(
                        "End Date must be same as Start Date. Only time can change."
                    )

            local_dt = fields.Datetime.context_timestamp(self, rec.start_datetime)

            #  Past Date
            if local_dt < fields.Datetime.context_timestamp(
                self, fields.Datetime.now()
            ):
                raise ValidationError("You cannot select past date or time.")

            # Sunday Closed
            if local_dt.weekday() == 6:
                raise ValidationError("Hospital closed on Sunday.")

            # Public Holiday
            holiday = self.env["resource.calendar.leaves"].search(
                [
                    ("date_from", "<=", rec.start_datetime),
                    ("date_to", ">=", rec.start_datetime),
                    ("company_id", "=", self.env.company.id),
                ],
                limit=1,
            )

            if holiday:
                raise ValidationError("Hospital closed on Public Holiday.")

            #  Doctor Calendar
            calendar = rec.doctor_id.resource_calendar_id
            if not calendar:
                raise ValidationError("Doctor working schedule not set.")

            weekday = str(local_dt.weekday())
            appointment_time = local_dt.hour + local_dt.minute / 60.0
            slot = rec.doctor_id.slot_duration or 15
            matched = False

            for att in calendar.attendance_ids:
                if att.dayofweek != weekday:
                    continue
                if not (att.hour_from <= appointment_time < att.hour_to):
                    continue

                start_minutes = int(att.hour_from * 60)
                appointment_minutes = int(local_dt.hour * 60 + local_dt.minute)

                #  Slot Interval Check
                if (appointment_minutes - start_minutes) % slot != 0:
                    raise ValidationError(
                        f"Appointment must follow {slot} minute slot interval."
                    )

                matched = True
                break

            if not matched:
                raise ValidationError("Doctor not available at selected time.")

            #  Doctor Overlap
            doctor_overlap = self.search(
                [
                    ("id", "!=", rec.id),
                    ("state", "!=", "cancel"),
                    ("doctor_id", "=", rec.doctor_id.id),
                    ("start_datetime", "<", rec.end_datetime),
                    ("end_datetime", ">", rec.start_datetime),
                ],
                limit=1,
            )

            if doctor_overlap:
                raise ValidationError("Doctor already booked at this time.")

            #  Patient Overlap
            patient_overlap = self.search(
                [
                    ("id", "!=", rec.id),
                    ("state", "!=", "cancel"),
                    ("patient_id", "=", rec.patient_id.id),
                    ("start_datetime", "<", rec.end_datetime),
                    ("end_datetime", ">", rec.start_datetime),
                ],
                limit=1,
            )

            if patient_overlap:
                raise ValidationError("Patient already has appointment at this time.")

    # STATE ACTIONS 

    def action_requested(self):
        for rec in self:

            rec.state = "request"

            template = self.env.ref(
                "hospital_management.email_template_appointment_request",
                raise_if_not_found=False,
            )

            if not template:
                raise ValidationError("Request Template Not Found")


            template.send_mail(rec.id, force_send=True)



    def action_confirm(self):
        for rec in self:

            _logger.debug("CONFIRM BUTTON CLICKED")

            rec.state = "confirm"

            # CREATE INVOICE
            if not rec.invoice_id:

                invoice = self.env["account.move"].create(
                    {
                        "move_type": "out_invoice",
                        "partner_id": rec.patient_id.partner_id.id,
                        "ref": rec.name,
                        "invoice_origin": rec.name,
                        "company_id": rec.company_id.id,
                        "currency_id": rec.currency_id.id,
                        "invoice_line_ids": [
                            (
                                0,
                                0,
                                {
                                    "name": "Consultation Fee",
                                    "quantity": 1,
                                    "price_unit": rec.consultation_fee,
                                },
                            )
                        ],
                    }
                )

                # POST INVOICE
                invoice.action_post()

                # CREATE PORTAL TOKEN
                invoice._portal_ensure_token()

                rec.invoice_id = invoice

            # SEND EMAIL
            template = self.env.ref(
                "hospital_management.email_template_appointment_status",
                raise_if_not_found=False,
            )

            if not template:
                raise ValidationError("Confirm Template Not Found")

            template.send_mail(rec.id, force_send=True, raise_exception=False)

    def action_consult(self):
        self.state = "consult"

    def action_done(self):
        for rec in self:
            if rec.state == "consult":
                if not rec.doc_description:
                    raise UserError("please add consultation description befor Done")
                rec.state = "done"

    def action_cancel(self):
        return {
            "name": "Cancel Appointment",
            "type": "ir.actions.act_window",
            "res_model": "appointment.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_appointment_id": self.id},
        }

    def action_reset_to_draft(self):
        for rec in self:
            rec.state = "draft"

    # REMINDER 

    def action_send_appointment_reminder(self):

        reminder_days = self.env.company.reminder_days

        template = self.env.ref(
            "hospital_management.email_template_appointment_reminder",
            raise_if_not_found=False,
        )

        if not template:
            _logger.error("REMINDER TEMPLATE NOT FOUND")
            return

        now = fields.Datetime.now()
        target_date = (now + timedelta(days=reminder_days)).date()

        start_dt = fields.Datetime.to_datetime(f"{target_date} 00:00:00")
        end_dt = fields.Datetime.to_datetime(f"{target_date} 23:59:59")

        appointments = self.search(
            [
                ("state", "=", "confirm"),
                ("start_datetime", ">=", start_dt),
                ("start_datetime", "<=", end_dt),
                ("reminder_sent", "=", False),
            ]
        )

        for rec in appointments:
            if rec.patient_id.email:
                template.send_mail(rec.id, force_send=True)

                rec.message_post(
                    body=_("Appointment reminder email sent to Patient."),
                    subtype_xmlid="mail.mt_comment",
                )

                rec.reminder_sent = True
                _logger.info("REMINDER SENT FOR %s", rec.name)

    
    @api.onchange('specialization_id')
    def _onchange_specialization_id(self):
        if self.specialization_id and self.doctor_id and self.doctor_id.specialization_id != self.specialization_id:
            self.doctor_id = False

    @api.onchange('doctor_id')
    def _onchange_doctor_id(self):
        if self.doctor_id:
            self.specialization_id = self.doctor_id.specialization_id.id

    def write(self, vals):
        if 'state' in vals:
            new_state = vals['state']
            is_hospital_admin = self.env.user.has_group('hospital_management.group_admin')

            for rec in self:
                old_state = rec.state
                
                if not is_hospital_admin:
                    # Required Description for Done
                    if new_state == 'done' and not rec.doc_description:
                        raise UserError("Action Required: Please provide the Consultation Description before setting the status to 'Done'.")

                    # Required Reason for Cancel
                    if new_state == 'cancel' and not rec.cancel_reason:
                        raise UserError("Action Required: A Cancellation Reason must be provided to cancel this appointment.")

                allowed_transitions = {
                    'draft': ['request', 'cancel'],
                    'request': ['confirm', 'cancel'],
                    'confirm': ['consult', 'cancel'],
                    'consult': ['done'],
                    'done': [],
                    'cancel': ['draft'],
                }
                
                if new_state not in allowed_transitions.get(old_state, []):
                    raise UserError(f"Access Restricted: You cannot move the appointment from '{old_state.capitalize()}' to '{new_state.capitalize()}' directly.")

        return super(HospitalAppointment, self).write(vals)