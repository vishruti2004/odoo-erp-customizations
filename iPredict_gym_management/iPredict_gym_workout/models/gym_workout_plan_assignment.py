from odoo import fields, models


class GymWorkoutAssignment(models.Model):
    _name = "gym.workout.assignment"
    _description = "Workout Assignment"
    _order = "start_date desc"

    member_id = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade")
    plan_id = fields.Many2one("gym.workout.plan", string="Workout Plan", required=True, ondelete="cascade")
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    days = fields.Integer(related="plan_id.days", string="Days", store=True, readonly=True)