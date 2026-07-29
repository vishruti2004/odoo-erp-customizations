from datetime import timedelta
from odoo import api, fields, models


class GymDietAssignment(models.Model):
    _name = "gym.diet.assignment"
    _description = "Diet Assignment"
    _order = "start_date desc"

    member_id = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade", domain=[('is_gym_member', '=', True)])
    plan_id = fields.Many2one("gym.diet.plan", string="Diet Plan", required=True, ondelete="cascade")
    trainer_id = fields.Many2one("res.partner", string="Trainer", readonly=True, default=lambda self: self.env.user.partner_id)
    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", required=True)
    state = fields.Selection([("active", "Active"), ("expiring", "Expiring Soon"), ("expired", "Expired")], string="Status", default="active", required=True)

    @api.model
    def _cron_update_diet_assignment_status(self):
        today = fields.Date.today()

        assignments = self.search([])

        for rec in assignments:
            if rec.end_date < today:
                rec.state = "expired"
            elif rec.end_date <= today + timedelta(days=3):
                rec.state = "expiring"
            else:
                rec.state = "active"