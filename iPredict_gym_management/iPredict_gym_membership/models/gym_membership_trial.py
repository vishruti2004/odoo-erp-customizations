# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import Command, api, fields, models, _
from odoo.exceptions import ValidationError


class GymMembershipTrial(models.Model):
    _name = "gym.membership.trial"
    _description = "Gym Membership Trial"
    _order = "start_date desc, id desc"

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default="New")
    customer_id = fields.Many2one("res.partner", string="Customer", required=True, ondelete="restrict", domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    membership_plan_id = fields.Many2one("gym.membership.plan", string="Membership", required=True, ondelete="restrict", domain="['&', ('is_trial', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    amount = fields.Monetary(string="Trial Amount", currency_field="currency_id", required=True, default=0.0, readonly=True)
    start_date = fields.Date(string="Start Date", required=True, default=fields.Date.context_today)
    end_date = fields.Date(string="End Date", compute="_compute_end_date", store=True, readonly=True)
    state = fields.Selection([("draft", "Draft"), ("active", "Active"), ("member_created", "Membership Created"), ("cancelled", "Cancelled")], string="Status", required=True, default="draft")
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one("res.currency", string="Currency", related="company_id.currency_id", store=True, readonly=True)
    sale_order_id = fields.Many2one("sale.order", string="Sale Order", readonly=True, copy=False)

    @api.depends(
        "start_date",
        "membership_plan_id",
        "membership_plan_id.trial_days",
    )
    def _compute_end_date(self):
        for record in self:
            if (
                record.start_date
                and record.membership_plan_id
                and record.membership_plan_id.trial_days > 0
            ):
                record.end_date = record.start_date + timedelta(
                    days=record.membership_plan_id.trial_days
                )
            else:
                record.end_date = False

    @api.constrains("start_date")
    def _check_start_date(self):
        today = fields.Date.context_today(self)

        for record in self:
            if record.start_date and record.start_date < today:
                raise ValidationError(
                    _("Start Date cannot be in the past.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals["company_id"] = self.env.company.id

            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code(
                        "gym.membership.trial"
                    )
                    or "New"
                )

            vals["amount"] = 0.0

        return super().create(vals_list)

    @api.constrains("start_date", "end_date")
    def _check_trial_dates(self):
        for record in self:
            if (
                record.start_date
                and record.end_date
                and record.end_date < record.start_date
            ):
                raise ValidationError(
                    _("End Date cannot be earlier than Start Date.")
                )

    @api.constrains("membership_plan_id", "company_id")
    def _check_trial_membership_plan(self):
        for record in self:
            if (
                record.membership_plan_id
                and not record.membership_plan_id.is_trial
            ):
                raise ValidationError(
                    _(
                        "Only Membership Plans marked as Trial Membership "
                        "can be selected."
                    )
                )

            if (
                record.membership_plan_id
                and record.membership_plan_id.company_id
                and record.membership_plan_id.company_id
                != record.company_id
            ):
                raise ValidationError(
                    _("Membership Plan and Company must be the same.")
                )

    def action_confirm_trial(self):
        for record in self:
            if record.state == "draft":
                record.state = "active"

    def action_cancel_trial(self):
        for record in self:
            if record.state not in ("member_created", "cancelled"):
                record.state = "cancelled"

    def action_convert_to_gym_member(self):
        self.ensure_one()

        if self.state != "active":
            return False

        if self.sale_order_id:
            return {
                "type": "ir.actions.act_window",
                "name": _("Sale Order"),
                "res_model": "sale.order",
                "view_mode": "form",
                "res_id": self.sale_order_id.id,
                "target": "current",
            }

        plan = self.membership_plan_id

        if not plan:
            raise ValidationError(
                _("Please select a Membership Plan first.")
            )

        if not plan.is_trial:
            raise ValidationError(
                _(
                    "Only Membership Plans marked as Trial Membership "
                    "can be converted."
                )
            )

        if (
            plan.company_id
            and plan.company_id != self.company_id
        ):
            raise ValidationError(
                _("The selected Membership Plan does not belong to this company.")
            )

        product_variant = plan.product_id.product_variant_id

        if not product_variant:
            product_variant = plan.product_id.product_variant_ids[:1]

        if not product_variant:
            raise ValidationError(
                _("No product variant found for this membership plan.")
            )

        order = self.env["sale.order"].with_company(
            self.company_id
        ).create({
            "partner_id": self.customer_id.id,
            "company_id": self.company_id.id,
            "order_line": [
                Command.create({
                    "product_id": product_variant.id,
                    "product_uom_qty": 1.0,
                    "price_unit": plan.price,
                })
            ],
        })

        self.write({
            "sale_order_id": order.id,
            "state": "member_created",
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Membership Sale Order"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": order.id,
            "target": "current",
        }