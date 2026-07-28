from odoo import fields, models


class GymDietAssignment(models.Model):
    _name = "gym.diet.assignment"
    _description = "Diet Assignment"
    _order = "start_date desc"

    member_id = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade")
    plan_id = fields.Many2one("gym.diet.plan", string="Diet Plan", required=True, ondelete="cascade")
    trainer_id = fields.Many2one("res.partner", string="Assigned By", readonly=True, default=lambda self: self.env.user.partner_id)
    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)