# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    membership_plan_id = fields.Many2one("gym.membership.plan", string="Membership Plan", tracking=True, domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    work_schedule_id = fields.Many2one("resource.calendar", string="Work Schedule", tracking=True)
    auto_renew = fields.Boolean(string="Auto Renew", tracking=True)
    is_frozen = fields.Boolean(string="Membership Frozen", tracking=True)
    freeze_start_date = fields.Date(string="Freeze Start", tracking=True)
    freeze_end_date = fields.Date(string="Freeze End", tracking=True)
    freeze_days = fields.Integer(string="Freeze Days", compute="_compute_freeze_days", store=True)
    membership_freeze_extension_days = fields.Integer(string="Freeze Extension Days", default=0, copy=False)
    remaining_days = fields.Integer(string="Remaining Days", compute="_compute_remaining_days", store=True)
    notes = fields.Text(string="Gym Notes")
    membership_start_date = fields.Date(string="Start Date", tracking=True)
    membership_end_date = fields.Date(string="End Date", compute="_compute_membership_end_date", store=True, tracking=True)
    is_gym_member = fields.Boolean(string="Gym Member", default=False, tracking=True)
    membership_history_ids = fields.One2many("gym.membership.history", "member_id", string="Membership History")
    member_code = fields.Char(string="Member ID", readonly=True, copy=False, index=True)
    create_employee_for_member = fields.Boolean(string="Create Employee for Member", related="company_id.gym_create_employee_for_member", readonly=True)
    trainer_id = fields.Many2many("hr.employee", string="Trainer", domain="[('is_trainer', '=', True), ('company_id', '=', company_id)]")
    attendance_employee_id = fields.Many2one("hr.employee", string="Attendance Employee", copy=False, domain="[('company_id', '=', company_id)]")

    @api.depends("freeze_start_date", "freeze_end_date")
    def _compute_freeze_days(self):
        for record in self:
            record.freeze_days = 0
            if record.freeze_start_date and record.freeze_end_date:
                record.freeze_days = (
                    record.freeze_end_date - record.freeze_start_date
                ).days + 1

    @api.depends(
        "membership_start_date",
        "membership_plan_id.duration",
        "membership_plan_id.duration_uom",
        "membership_freeze_extension_days",
    )
    def _compute_membership_end_date(self):
        for record in self:
            record.membership_end_date = False

            if not record.membership_start_date or not record.membership_plan_id:
                continue

            duration = record.membership_plan_id.duration
            unit = record.membership_plan_id.duration_uom

            if unit == "days":
                end_date = record.membership_start_date + timedelta(days=duration)
            elif unit == "months":
                end_date = fields.Date.add(
                    record.membership_start_date,
                    months=duration,
                )
            elif unit == "years":
                end_date = fields.Date.add(
                    record.membership_start_date,
                    years=duration,
                )
            else:
                continue

            record.membership_end_date = end_date + timedelta(
                days=record.membership_freeze_extension_days
            )

    @api.depends("membership_end_date")
    def _compute_remaining_days(self):
        today = fields.Date.today()

        for record in self:
            record.remaining_days = 0

            if record.membership_end_date:
                remaining = (record.membership_end_date - today).days
                record.remaining_days = max(remaining, 0)

    @api.constrains(
        "is_gym_member",
        "company_id",
        "membership_plan_id",
        "trainer_id",
        "attendance_employee_id",
    )
    def _check_gym_member_company(self):
        for record in self:
            if not record.company_id:
                continue

            company = record.company_id

            if (
                record.membership_plan_id
                and record.membership_plan_id.company_id
                and record.membership_plan_id.company_id != company
            ):
                raise ValidationError(
                    _(
                        "The Membership Plan must belong to the same company as the member."
                    )
                )

            wrong_trainers = record.trainer_id.filtered(
                lambda emp: emp.company_id != company
            )
            if wrong_trainers:
                raise ValidationError(
                    _(
                        "All assigned trainers must belong to the same company as the member."
                    )
                )

            if (
                record.attendance_employee_id
                and record.attendance_employee_id.company_id != company
            ):
                raise ValidationError(
                    _(
                        "The Attendance Employee must belong to the same company as the member."
                    )
                )

    def action_freeze_membership(self):
        self.ensure_one()

        active_membership = self.env["gym.membership.history"].search(
            [
                ("member_id", "=", self.id),
                ("status", "=", "active"),
                ("company_id", "=", self.company_id.id),
            ],
            order="membership_start_date desc, id desc",
            limit=1,
        )

        if not active_membership:
            raise ValidationError(
                _(
                    "This member does not have an active membership in the current company."
                )
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Freeze Membership"),
            "res_model": "gym.membership.freeze.wizard",
            "view_mode": "form",
            "view_id": self.env.ref(
                "iPredict_gym_membership.view_gym_membership_freeze_wizard_form"
            ).id,
            "target": "new",
            "context": {
                "default_partner_id": self.id,
                "default_membership_history_id": active_membership.id,
            },
        }

    def action_assign_locker(self):
        self.ensure_one()

        if not self.is_gym_member:
            raise ValidationError(
                _("Only gym members can be assigned a locker.")
            )

        if not self.company_id:
            raise ValidationError(
                _("Please assign a company to this gym member first.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Locker"),
            "res_model": "gym.member.locker.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_member_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_create_attendance_employee(self):
        self.ensure_one()

        if not self.is_gym_member:
            raise ValidationError(
                _("Only gym members can create an attendance employee.")
            )

        if not self.company_id:
            raise ValidationError(
                _(
                    "Please assign a company to this gym member "
                    "before creating an employee."
                )
            )

        company = self.company_id

        if not company.gym_create_employee_for_member:
            raise ValidationError(
                _(
                    "Creating an employee for gym members is not enabled "
                    "in Settings for %s."
                )
                % company.name
            )

        if self.attendance_employee_id:
            raise ValidationError(
                _("An attendance employee already exists for this member.")
            )

        Department = self.env["hr.department"]
        Employee = self.env["hr.employee"]

        department = Department.search(
            [
                ("name", "=", "Gym Members"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )

        if not department:
            department = Department.create(
                {
                    "name": "Gym Members",
                    "company_id": company.id,
                }
            )

        employee = Employee.create(
            {
                "name": self.name,
                "company_id": company.id,
                "department_id": department.id,
                "work_contact_id": self.id,
                "active": True,
            }
        )

        self.write({
            "attendance_employee_id": employee.id,
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Employee Created"),
                "message": _(
                    "Attendance employee has been created for %s."
                ) % self.name,
                "type": "success",
                "sticky": False,
            },
        }