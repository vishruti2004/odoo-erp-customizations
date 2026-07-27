# -*- coding: utf-8 -*-

from odoo import api, fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    is_trainer = fields.Boolean(string="Is Trainer", default=False)
    trainer_code = fields.Char(string="Trainer ID", readonly=True, copy=False)
    skill_ids = fields.Many2many("hr.skill", string="Skills")
    member_ids = fields.Many2many("res.partner", string="Assigned Members", domain="[('is_gym_member', '=', True)]")
    member_count = fields.Integer(string="Members", compute="_compute_member_count", store=False)


    @api.depends("member_ids")
    def _compute_member_count(self):
        for trainer in self:
            trainer.member_count = len(trainer.member_ids)

    # CREATE / SEQUENCE

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("trainer_code"):
                vals["trainer_code"] = self.env["ir.sequence"].next_by_code("gym.trainer")
        return super().create(vals_list)

    # ACTION METHODS

    def action_view_assigned_members(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Assigned Members",
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("id", "in", self.member_ids.ids)],
            "context": {
                "default_trainer_id": self.id,
            },
            "target": "current",
        }