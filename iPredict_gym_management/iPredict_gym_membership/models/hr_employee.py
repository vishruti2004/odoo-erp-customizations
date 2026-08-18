# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    is_trainer = fields.Boolean(string="Is Trainer", default=False)
    trainer_code = fields.Char(string="Trainer ID", readonly=True, copy=False)
    skill_ids = fields.Many2many("hr.skill", string="Gym Skills")
    member_ids = fields.Many2many("res.partner", string="Assigned Members", domain="[('is_gym_member', '=', True), ('company_id', '=', company_id)]")
    member_count = fields.Integer(string="Members", compute="_compute_member_count", store=False)

    @api.depends("member_ids")
    def _compute_member_count(self):
        for trainer in self:
            trainer.member_count = len(trainer.member_ids)

    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env["ir.sequence"].sudo()
        Company = self.env["res.company"]

        for vals in vals_list:
            if vals.get("trainer_code"):
                continue

            company_id = vals.get("company_id") or self.env.company.id
            company = Company.browse(company_id)

            sequence = Sequence.search(
                [
                    ("code", "=", "gym.trainer"),
                    ("company_id", "=", company_id),
                ],
                limit=1,
            )

            if not sequence:
                sequence = Sequence.create({
                    "name": f"Gym User - {company.name}",
                    "code": "gym.trainer",
                    "prefix": "TR",
                    "padding": 4,
                    "number_increment": 1,
                    "company_id": company_id,
                })

            vals["trainer_code"] = sequence.next_by_id()

        return super().create(vals_list)

    def action_view_assigned_members(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Assigned Members",
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [
                ("id", "in", self.member_ids.ids),
                ("company_id", "=", self.company_id.id),
            ],
            "context": {
                "default_trainer_id": self.id,
            },
            "target": "current",
        }