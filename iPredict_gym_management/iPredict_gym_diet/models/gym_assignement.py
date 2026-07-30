from datetime import timedelta
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
    is_renewed = fields.Boolean(string="Renewed", default=False, copy=False)

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

    def action_renew_diet(self):
        self.ensure_one()

        today = fields.Date.today()

        self.write({
            "is_renewed": True,
        })

        # Create new active diet plan
        new_assignment = self.create({
            "member_id": self.member_id.id,
            "plan_id": self.plan_id.id,
            "trainer_id": self.env.user.partner_id.id,
            "start_date": today,
            "end_date": today + timedelta(days=self.plan_id.days - 1),
            "state": "active",
            "is_renewed": False,
        })

        # Chatter message
        new_assignment.member_id.message_post(
            subject=_("Diet Plan Renewed"),
            body=_(
                "Diet Plan: %s\n"
                "Renewed By: %s\n"
                "Start Date: %s\n"
                "End Date: %s"
            ) % (
                new_assignment.plan_id.name,
                self.env.user.partner_id.name,
                new_assignment.start_date,
                new_assignment.end_date,
            ),
        )

        return True