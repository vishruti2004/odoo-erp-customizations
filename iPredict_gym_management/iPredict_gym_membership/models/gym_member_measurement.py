# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GymMemberMeasurement(models.Model):
    _name = "gym.member.measurement"
    _description = "Member Body Measurement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "measurement_date desc, id desc"

    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, index=True)
    member_ids = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade", tracking=True, domain="['&', ('is_gym_member', '=', True), ('membership_history_ids.company_id', '=', company_id)]")
    measurement_date = fields.Date(string="Date", required=True, default=fields.Date.today, tracking=True)
    gender = fields.Selection([("male", "Male"), ("female", "Female")], string="Gender", required=True, default="male", tracking=True)
    age = fields.Integer(string="Age", tracking=True)
    weight = fields.Float(string="Weight (kg)", tracking=True)
    height = fields.Float(string="Height (cm)", tracking=True)
    neck = fields.Float(string="Neck (cm)", tracking=True)
    biceps = fields.Float(string="Biceps (cm)", tracking=True)
    calf = fields.Float(string="Calf (cm)", tracking=True)
    hips = fields.Float(string="Hips (cm)", tracking=True)
    chest = fields.Float(string="Chest (cm)", tracking=True)
    waist = fields.Float(string="Waist (cm)", tracking=True)
    forearm = fields.Float(string="Forearm (cm)", tracking=True)
    shoulder = fields.Float(string="Shoulder (cm)", tracking=True)
    thigh = fields.Float(string="Thigh (cm)", tracking=True)
    bmi = fields.Float(string="BMI", compute="_compute_bmi_bmr", store=True)
    bmr = fields.Float(string="BMR", compute="_compute_bmi_bmr", store=True)

    @api.depends("weight", "height", "gender", "age")
    def _compute_bmi_bmr(self):
        for record in self:
            # BMI
            if record.height and record.height > 0 and record.weight:
                height_m = record.height / 100
                record.bmi = record.weight / (height_m * height_m)
            else:
                record.bmi = 0.0

            # BMR
            if record.weight and record.height and record.age:
                weight_kg = record.weight
                height_cm = record.height
                age = record.age

                if record.gender == "male":
                    record.bmr = (
                        (10 * weight_kg)
                        + (6.25 * height_cm)
                        - (5 * age)
                        + 5
                    )
                else:
                    record.bmr = (
                        (10 * weight_kg)
                        + (6.25 * height_cm)
                        - (5 * age)
                        - 161
                    )
            else:
                record.bmr = 0.0

    @api.constrains("member_ids", "company_id")
    def _check_company(self):
        MembershipHistory = self.env["gym.membership.history"]

        for record in self:
            if not record.member_ids or not record.company_id:
                continue

            membership = MembershipHistory.search(
                [
                    ("member_id", "=", record.member_ids.id),
                    ("company_id", "=", record.company_id.id),
                ],
                limit=1,
            )

            if not membership:
                raise ValidationError(
                    _(
                        "The selected member does not have a membership "
                        "in the selected company."
                    )
                )

    @api.constrains("weight", "height", "age")
    def _check_positive_values(self):
        for record in self:
            if record.weight and record.weight <= 0:
                raise ValidationError(
                    _("Weight must be greater than 0.")
                )

            if record.height and record.height <= 0:
                raise ValidationError(
                    _("Height must be greater than 0.")
                )

            if record.age and record.age <= 0:
                raise ValidationError(
                    _("Age must be greater than 0.")
                )

    def action_view_member(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Member"),
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.member_ids.id,
            "target": "current",
        }