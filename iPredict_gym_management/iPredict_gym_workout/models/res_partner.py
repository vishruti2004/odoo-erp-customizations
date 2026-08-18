# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    workout_plan_ids = fields.Many2many("gym.workout.plan", string="Workout Plans", compute="_compute_workout_plans", store=False)
    workout_plan_history_ids = fields.Many2many("gym.workout.plan", string="Workout Plan History", compute="_compute_workout_plans", store=False)
    workout_assignment_ids = fields.One2many("gym.workout.assignment", "member_id", string="Workout History")

    def _compute_workout_plans(self):
        Assignment = self.env["gym.workout.assignment"]

        for partner in self:
            assignments = Assignment.search([
                ("member_id", "=", partner.id),
                ("company_id", "=", partner.company_id.id),
            ])

            plans = assignments.mapped("plan_id")

            partner.workout_plan_ids = plans
            partner.workout_plan_history_ids = plans