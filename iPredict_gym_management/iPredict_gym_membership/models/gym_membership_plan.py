# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class GymMembershipPlan(models.Model):
    _name = "gym.membership.plan"
    _description = "Gym Membership Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(string="Plan Name", required=True, tracking=True)
    product_id = fields.Many2one("product.template", string="Product", required=True, tracking=True)
    duration = fields.Integer(string="Duration", required=True, default=1, tracking=True)
    duration_uom = fields.Selection([("days", "Days"), ("months", "Months"), ("years", "Years")], string="Duration Unit", default="months", required=True, tracking=True)
    price = fields.Monetary(string="Price", currency_field="currency_id", required=True, tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one("res.currency", string="Currency", related="company_id.currency_id", store=True, readonly=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)

    _sql_constraints = [
        (
            "unique_plan_name_company",
            "unique(name, company_id)",
            "Membership Plan name must be unique per company.",
        ),
    ]