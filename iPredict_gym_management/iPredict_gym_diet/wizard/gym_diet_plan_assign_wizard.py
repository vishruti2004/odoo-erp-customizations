from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymDietPlanAssignWizard(models.TransientModel):
    _name = "gym.diet.plan.assign.wizard"
    _description = "Assign Diet Plan Wizard"

    # ---------------------------------------------------------
    # COMPANY
    # ---------------------------------------------------------

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        readonly=True,
        default=lambda self: self.env.company,
    )

    # ---------------------------------------------------------
    # DIET PLAN
    # ---------------------------------------------------------

    plan_id = fields.Many2one(
        "gym.diet.plan",
        string="Diet Plan",
        required=True,
        domain="[('company_id', '=', company_id)]",
    )

    # ---------------------------------------------------------
    # MEMBERS
    # ---------------------------------------------------------

    member_ids = fields.Many2many(
        "res.partner",
        string="Assign To",
        domain="[('is_gym_member', '=', True), ('company_id', '=', company_id)]",
    )

    # ---------------------------------------------------------
    # DATES
    # ---------------------------------------------------------

    start_date = fields.Date(
        string="Date From",
        required=True,
        default=fields.Date.today,
    )

    end_date = fields.Date(
        string="Date To",
    )

    # ---------------------------------------------------------
    # DEFAULT VALUES
    # ---------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        company = self.env.company
        res["company_id"] = company.id

        user = self.env.user

        if (
            user.has_group("iPredict_gym_base.group_gym_user")
            and not user.has_group("iPredict_gym_base.group_gym_admin")
        ):
            trainer = user.employee_id

            if trainer:
                members = trainer.member_ids.filtered(
                    lambda member:
                        member.is_gym_member
                        and member.company_id == company
                )

                res["member_ids"] = [
                    (6, 0, members.ids)
                ]

        return res

    # ---------------------------------------------------------
    # ONCHANGE
    # ---------------------------------------------------------

    @api.onchange("plan_id", "start_date")
    def _onchange_dates(self):
        if self.plan_id and self.start_date:

            # Make sure selected plan belongs to wizard company
            if self.plan_id.company_id != self.company_id:
                self.plan_id = False
                self.end_date = False
                return {
                    "warning": {
                        "title": _("Invalid Diet Plan"),
                        "message": _(
                            "The selected Diet Plan does not belong "
                            "to the current company."
                        ),
                    }
                }

            self.end_date = self.plan_id.get_end_date(
                self.start_date
            )

        else:
            self.end_date = False

    # ---------------------------------------------------------
    # ASSIGN DIET PLAN
    # ---------------------------------------------------------

    def action_assign(self):
        self.ensure_one()

        # -----------------------------------------------------
        # BASIC VALIDATION
        # -----------------------------------------------------

        if not self.company_id:
            raise ValidationError(
                _("Company is required.")
            )

        if not self.plan_id:
            raise ValidationError(
                _("Please select a Diet Plan.")
            )

        if not self.member_ids:
            raise ValidationError(
                _("Please select at least one member.")
            )

        if not self.start_date:
            raise ValidationError(
                _("Please select a start date.")
            )

        if not self.end_date:
            self.end_date = self.plan_id.get_end_date(
                self.start_date
            )

        if self.start_date < fields.Date.today():
            raise ValidationError(
                _("Past dates are not allowed.")
            )

        # -----------------------------------------------------
        # PLAN COMPANY VALIDATION
        # -----------------------------------------------------

        if self.plan_id.company_id != self.company_id:
            raise ValidationError(
                _(
                    "The selected Diet Plan does not belong "
                    "to the current company."
                )
            )

        # -----------------------------------------------------
        # MEMBER COMPANY VALIDATION
        # -----------------------------------------------------

        invalid_members = self.member_ids.filtered(
            lambda member:
                not member.is_gym_member
                or member.company_id != self.company_id
        )

        if invalid_members:
            raise ValidationError(
                _(
                    "The following members do not belong "
                    "to the current company or are not gym members:\n%s"
                )
                % ", ".join(invalid_members.mapped("name"))
            )

        # -----------------------------------------------------
        # ASSIGNMENT
        # -----------------------------------------------------

        assignment_obj = self.env["gym.diet.assignment"]

        for member in self.member_ids:

            existing_assignment = assignment_obj.search(
                [
                    ("member_id", "=", member.id),
                    ("plan_id", "=", self.plan_id.id),
                    ("company_id", "=", self.company_id.id),
                    ("start_date", "<=", self.end_date),
                    ("end_date", ">=", self.start_date),
                ],
                limit=1,
            )

            if existing_assignment:
                raise ValidationError(
                    _(
                        "Diet plan '%(plan)s' is already assigned "
                        "to %(member)s during the selected period."
                    )
                    % {
                        "plan": self.plan_id.name,
                        "member": member.name,
                    }
                )

            assignment_obj.create(
                {
                    "member_id": member.id,
                    "plan_id": self.plan_id.id,
                    "trainer_id": self.env.user.partner_id.id,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                }
            )

        # -----------------------------------------------------
        # CHATTER
        # -----------------------------------------------------

        self.plan_id.message_post(
            subject=_("Diet Plan Assigned"),
            body=_(
                "Company      : %(company)s\n"
                "Assigned To  : %(members)s\n"
                "Start Date   : %(start)s\n"
                "End Date     : %(end)s\n"
                "Assigned By  : %(user)s"
            )
            % {
                "company": self.company_id.name,
                "members": ", ".join(
                    self.member_ids.mapped("name")
                ),
                "start": self.start_date.strftime(
                    "%d/%m/%Y"
                ),
                "end": self.end_date.strftime(
                    "%d/%m/%Y"
                ),
                "user": self.env.user.name,
            },
        )

        return {
            "type": "ir.actions.act_window_close"
        }

    # ---------------------------------------------------------
    # CANCEL
    # ---------------------------------------------------------

    def action_cancel(self):
        return {
            "type": "ir.actions.act_window_close"
        }