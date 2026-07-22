# -*- coding: utf-8 -*-

from odoo import fields, models,api


class GymMembershipHistory(models.Model):
    _name = "gym.membership.history"
    _description = "Gym Membership History"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "membership_start_date desc, id desc"

    member_id = fields.Many2one(
        "res.partner",
        string="Member",
        required=True,
        ondelete="cascade",
        tracking=True,
    )

    membership_plan_id = fields.Many2one(
        "gym.membership.plan",
        string="Membership Plan",
        required=True,
        tracking=True,
    )

    membership_start_date = fields.Date(
        string="Start Date",
        required=True,
        tracking=True,
    )

    membership_end_date = fields.Date(
        string="End Date",
        required=True,
        tracking=True,
    )

    status = fields.Selection(
        [
            ("active", "Active"),
            ("frozen", "Frozen"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="active",
        required=True,
        tracking=True,
    )

    remark = fields.Text(
        string="Remark",
    )

    user_id = fields.Many2one(
        "res.users",
        string="Updated By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    name = fields.Char(
        string="Membership ID",
        readonly=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "gym.membership.history"
                )
        return super().create(vals_list)