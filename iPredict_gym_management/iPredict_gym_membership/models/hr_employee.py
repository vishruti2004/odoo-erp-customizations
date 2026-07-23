from odoo import fields, models, api

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    is_trainer = fields.Boolean(
        string="Is Trainer",
        default=False,
    )

    trainer_code = fields.Char(
        string="Trainer ID",
        readonly=True,
        copy=False,
    )

    skill_ids = fields.Many2many(
        "hr.skill",
        string="Skills",
    )

    member_ids = fields.Many2many(
        "res.partner",
        string="Assigned Members",
        domain="[('is_gym_member', '=', True)]",
    )
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('trainer_code'):
                vals['trainer_code'] = self.env['ir.sequence'].next_by_code('gym.trainer')
        return super().create(vals_list)