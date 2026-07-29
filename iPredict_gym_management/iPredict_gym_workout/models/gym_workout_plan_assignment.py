from odoo import api, fields, models

class GymWorkoutAssignment(models.Model):
    _name = "gym.workout.assignment"
    _description = "Workout Assignment"
    _order = "start_date desc"

    member_id = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade",        domain=[('is_gym_member', '=', True)],)
    plan_id = fields.Many2one("gym.workout.plan", string="Workout Plan", required=True, ondelete="cascade")
    trainer_id = fields.Many2one("res.partner", string="Assigned By", readonly=True, default=lambda self: self.env.user.partner_id)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)
    days = fields.Integer(related="plan_id.days", string="Days", store=True, readonly=True)