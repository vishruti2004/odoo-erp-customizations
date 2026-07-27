from odoo import fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    workout_plan_ids = fields.Many2many("gym.workout.plan", string="Workout Plans", compute="_compute_workout_plans", store=False)
    workout_plan_history_ids = fields.Many2many("gym.workout.plan", string="Workout Plan History", compute="_compute_workout_plans", store=False)
    workout_assignment_ids = fields.One2many("gym.workout.assignment", "member_id", string="Workout History")

    def _compute_workout_plans(self):
        for partner in self:
            plans = self.env["gym.workout.plan"].search([("member_ids", "in", partner.id)])
            partner.workout_plan_ids = plans
            partner.workout_plan_history_ids = plans