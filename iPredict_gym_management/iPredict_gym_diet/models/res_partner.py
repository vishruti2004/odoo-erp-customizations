from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    diet_assignment_ids = fields.One2many("gym.diet.assignment", "member_id", string="Diet History")