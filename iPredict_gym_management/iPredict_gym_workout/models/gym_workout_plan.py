# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymWorkoutPlan(models.Model):
    _name = "gym.workout.plan"
    _description = "Workout Plan"
    _order = "id desc"

    name = fields.Char(string="Plan Name", required=True)
    code = fields.Char(string="Plan Code", readonly=True, copy=False, default="New")
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, index=True)
    days = fields.Integer(string="Workout Days", default=0)
    assignment_count = fields.Integer(string="Assigned Members", compute="_compute_assignment_count")
    exercise_line_ids = fields.One2many("gym.workout.plan.exercise.line", "plan_id", string="Exercise List")

    @api.depends("company_id")
    def _compute_assignment_count(self):
        assignment_obj = self.env["gym.workout.assignment"]

        for rec in self:
            assignments = assignment_obj.search([
                ("plan_id", "=", rec.id),
                ("company_id", "=", rec.company_id.id),
            ])

            member_ids = assignments.mapped("member_id").ids
            rec.assignment_count = len(set(member_ids))

    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env["ir.sequence"]
        Company = self.env["res.company"]

        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id
            vals["company_id"] = company_id

            if not vals.get("code") or vals["code"] == "New":
                company = Company.browse(company_id)

                sequence = Sequence.search(
                    [
                        ("code", "=", "gym.workout.plan"),
                        ("company_id", "=", company_id),
                    ],
                    limit=1,
                )

                if not sequence:
                    sequence = Sequence.create({
                        "name": f"Workout Plan - {company.name}",
                        "code": "gym.workout.plan",
                        "prefix": "WP",
                        "padding": 4,
                        "number_increment": 1,
                        "company_id": company_id,
                    })

                vals["code"] = sequence.next_by_id()

        return super().create(vals_list)

    @api.constrains("company_id")
    def _check_company(self):
        for record in self:
            if record.company_id and record.company_id != self.env.company:
                # This is not blocking multi-company backend operations.
                # Record rules will handle visibility.
                continue

    def action_open_assign_wizard(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Workout Plan"),
            "res_model": "gym.workout.plan.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_plan_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_view_assigned_members(self):
        self.ensure_one()

        assignments = self.env["gym.workout.assignment"].search([
            ("plan_id", "=", self.id),
            ("company_id", "=", self.company_id.id),
        ])

        member_ids = list(
            set(assignments.mapped("member_id").ids)
        )

        expired_member_ids = list(
            set(
                assignments.filtered(
                    lambda a: (
                        a.state == "expired"
                        and not a.is_renewed
                    )
                ).mapped("member_id").ids
            )
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Assigned Members"),
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [
                ("id", "in", member_ids),
                ("company_id", "=", self.company_id.id),
            ],
            "context": {
                "search_default_expired_workout": 1,
                "expired_workout_member_ids": expired_member_ids,
            },
        }


class GymWorkoutPlanExerciseLine(models.Model):
    _name = "gym.workout.plan.exercise.line"
    _description = "Workout Plan Exercise Line"
    _order = "day, sequence"

    plan_id = fields.Many2one("gym.workout.plan", string="Workout Plan", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", string="Company", related="plan_id.company_id", store=True, readonly=True, index=True)
    day = fields.Selection([("monday", "Monday"), ("tuesday", "Tuesday"), ("wednesday", "Wednesday"), ("thursday", "Thursday"), ("friday", "Friday"), ("saturday", "Saturday"), ("sunday", "Sunday")], string="Day", required=True, default="monday")
    exercise_id = fields.Many2one("gym.exercise", string="Exercise", required=True, domain="[('company_id', '=', company_id)]")
    sets = fields.Integer(string="Sets")
    reps = fields.Char(string="Reps")
    rest = fields.Char(string="Rest Time")
    sequence = fields.Integer(string="Sequence", default=10)
    exercise_step_ids = fields.Many2many("gym.exercise.step", compute="_compute_exercise_steps", string="Exercise Steps")
    exercise_image = fields.Image(related="exercise_id.image", string="Exercise Image", readonly=True)
    exercise_video_url = fields.Char(related="exercise_id.video_url", string="Video URL", readonly=True)

    @api.depends("exercise_id")
    def _compute_exercise_steps(self):
        for rec in self:
            rec.exercise_step_ids = rec.exercise_id.step_ids

    @api.constrains("plan_id", "exercise_id")
    def _check_company(self):
        for record in self:
            if (
                record.plan_id
                and record.exercise_id
                and record.plan_id.company_id
                != record.exercise_id.company_id
            ):
                raise ValidationError(
                    _(
                        "Workout Plan and Exercise must belong to the same company."
                    )
                )