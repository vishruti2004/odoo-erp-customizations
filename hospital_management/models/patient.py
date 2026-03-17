from odoo import models, fields, api


class HospitalPatient(models.Model):
    _name = "hospital.patient"
    _description = "Patient"
    _rec_name = "display_name"
    _order = "active desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    partner_id = fields.Many2one(
        "res.partner", string="Patient", required=True, ondelete="cascade"
    )

    user_id = fields.Many2one("res.users", string="User", readonly=True)

    name = fields.Char(related="partner_id.name", store=True, tracking=True)
    email = fields.Char(related="partner_id.email", store=True, tracking=True)
    phone = fields.Char(related="partner_id.phone", store=True, tracking=True)
    street = fields.Char(related="partner_id.street", store=True, tracking=True)
    city = fields.Char(related="partner_id.city", store=True, tracking=True)

    patient_code = fields.Char(
        string="Patient ID",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )

    active = fields.Boolean("Active", default=True, tracking=True)

    date_of_birth = fields.Date(string="Date of Birth", tracking=True)

    age = fields.Integer(
        string="Age", compute="_compute_age", store=True, tracking=True
    )

    gender = fields.Selection(
        [("male", "Male"), ("female", "Female"), ("other", "Other")],
        string="Gender",
        tracking=True,
    )

    blood_group = fields.Selection(
        [
            ("A+", "A+"),
            ("A-", "A-"),
            ("B+", "B+"),
            ("B-", "B-"),
            ("O+", "O+"),
            ("O-", "O-"),
            ("AB+", "AB+"),
            ("AB-", "AB-"),
        ],
        string="Blood Group",
        tracking=True,
    )

    patient_type = fields.Selection(
        [
            ("opd", "OPD"),
            ("emergency", "Emergency"),
            ("ipd", "IPD"),
        ],
        string="Patient Type",
        default="opd",
        tracking=True,
    )

    emergency_contact = fields.Char(string="Emergency Contact", tracking=True)
    medical_history = fields.Text(string="Medical History", tracking=True)

    appointment_ids = fields.One2many(
        "hospital.appointment", "patient_id", string="Appointments"
    )

    appointment_count = fields.Integer(
        string="Appointment Count", compute="_compute_appointment_count"
    )

    def _compute_appointment_count(self):
        for rec in self:
            rec.appointment_count = self.env["hospital.appointment"].search_count(
                [("patient_id", "=", rec.id)]
            )

    def action_open_appointments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Appointments",
            "res_model": "hospital.appointment",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }

    @api.depends("patient_code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.patient_code}] {rec.name}"

    # AGE COMPUTE

    @api.depends("date_of_birth")
    def _compute_age(self):
        from datetime import date

        for rec in self:
            if rec.date_of_birth:
                today = date.today()
                rec.age = (
                    today.year
                    - rec.date_of_birth.year
                    - (
                        (today.month, today.day)
                        < (rec.date_of_birth.month, rec.date_of_birth.day)
                    )
                )
            else:
                rec.age = 0


    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            if vals.get("patient_code", "New") == "New":
                vals["patient_code"] = (
                    self.env["ir.sequence"].next_by_code("hospital.patient") or "New"
                )

        records = super().create(vals_list)

        for rec in records:

            if rec.partner_id:
                rec.partner_id.write({"is_patient": True, "is_doctor": False})

            group_user = self.env.ref("base.group_user")
            group_patient = self.env.ref("hospital_management.group_patient")
            group_invoice = self.env.ref("account.group_account_invoice")
            # check user exit
            existing_user = (
                self.env["res.users"]
                .sudo()
                .search([("partner_id", "=", rec.partner_id.id)], limit=1)
            )

            if existing_user:
                rec.user_id = existing_user.id

            else:
                user = (
                    self.env["res.users"]
                    .sudo()
                    .create(
                        {
                            "name": rec.name,
                            "login": rec.email,
                            "partner_id": rec.partner_id.id,
                            "group_ids": [
                                (
                                    6,
                                    0,
                                    [group_user.id, group_patient.id, group_invoice.id],
                                )
                            ],
                        }
                    )
                )

                rec.user_id = user.id

                # SEND PASSWORD SETUP EMAIL
                user.action_reset_password()

        return records
