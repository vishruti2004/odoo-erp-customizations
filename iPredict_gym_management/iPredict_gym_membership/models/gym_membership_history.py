# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GymMembershipHistory(models.Model):
    _name = "gym.membership.history"
    _description = "Gym Membership History"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "membership_start_date desc, id desc"

    company_id = fields.Many2one("res.company", string="Company", related="member_id.company_id", store=True, readonly=True, index=True)
    member_id = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade", tracking=True, domain="[('is_gym_member', '=', True)]")
    member_code = fields.Char(related="member_id.member_code", store=True, string="Member Code")
    display_member_id = fields.Char(string="Member ID", compute="_compute_display_member_id", store=True)
    membership_plan_id = fields.Many2one("gym.membership.plan", string="Membership Plan", required=True, tracking=True, domain="[('company_id', '=', company_id)]")
    membership_start_date = fields.Date(string="Start Date", required=True, tracking=True)
    membership_end_date = fields.Date(string="End Date", required=True, tracking=True)
    status = fields.Selection([("active", "Active"), ("frozen", "Frozen"), ("expired", "Expired"), ("cancelled", "Cancelled")], string="Status", default="active", required=True, tracking=True)
    remark = fields.Text(string="Remark")
    user_id = fields.Many2one("res.users", string="Updated By", default=lambda self: self.env.user, readonly=True)
    name = fields.Char(string="Membership ID", readonly=True, copy=False)
    renewal_sale_order_id = fields.Many2one("sale.order", string="Renewal Order", readonly=True, help="Sale order created for renewing this membership.")
    is_renewable = fields.Boolean(string="Is Renewable", compute="_compute_is_renewable", store=False, help="True if membership is expired and no renewal order exists yet.")

    # COMPUTE
    @api.depends("member_code", "name")
    def _compute_display_member_id(self):
        for rec in self:
            if rec.member_code and rec.name:
                rec.display_member_id = f"{rec.member_code} - {rec.name}"
            else:
                rec.display_member_id = rec.member_code or rec.name or ""

    @api.depends("status", "renewal_sale_order_id")
    def _compute_is_renewable(self):
        for rec in self:
            rec.is_renewable = (
                rec.status == "expired"
                and not rec.renewal_sale_order_id
            )

    # CONSTRAINTS
    @api.constrains("member_id", "membership_plan_id")
    def _check_company(self):
        for record in self:
            if not record.member_id:
                continue

            member_company = record.member_id.company_id

            if (
                record.membership_plan_id
                and member_company
                and record.membership_plan_id.company_id != member_company
            ):
                raise ValidationError(
                    _(
                        "The Membership Plan and Member must belong "
                        "to the same company."
                    )
                )

    # CREATE
    @api.model_create_multi
    def create(self, vals_list):
        Sequence = self.env["ir.sequence"].sudo()

        for vals in vals_list:
            if vals.get("name"):
                continue

            company_id = vals.get("company_id")

            # company_id is related, so normally get company from member
            if not company_id and vals.get("member_id"):
                member = self.env["res.partner"].browse(
                    vals["member_id"]
                )
                company_id = member.company_id.id

            if not company_id:
                company_id = self.env.company.id

            sequence = Sequence.search(
                [
                    ("code", "=", "gym.membership.history"),
                    ("company_id", "=", company_id),
                ],
                limit=1,
            )

            if not sequence:
                company = self.env["res.company"].browse(company_id)

                sequence = Sequence.create({
                    "name": f"Membership History - {company.name}",
                    "code": "gym.membership.history",
                    "prefix": "MS",
                    "padding": 5,
                    "number_increment": 1,
                    "company_id": company_id,
                })

            vals["name"] = sequence.next_by_id()

        return super().create(vals_list)

    # CRON: AUTO EXPIRE
    @api.model
    def _cron_expire_memberships(self):
        today = fields.Date.context_today(self)
        Partner = self.env["res.partner"]

        # FIND MEMBERS WHOSE CURRENT MEMBERSHIP HAS EXPIRED
        expired_members = Partner.search([
            ("is_gym_member", "=", True),
            ("membership_end_date", "!=", False),
            ("membership_end_date", "<", today),
        ])

        for partner in expired_members:
            # FIND CURRENT ACTIVE MEMBERSHIP HISTORY
            membership_history = self.search([
                ("member_id", "=", partner.id),
                ("status", "=", "active"),
            ], order="membership_start_date desc, id desc", limit=1)

            # MARK HISTORY AS EXPIRED (This is required so the Renew button can appear)
            if membership_history:
                membership_history.write({
                    "status": "expired",
                    "user_id": self.env.user.id,
                    "remark": _(
                        "Membership automatically expired because "
                        "the member's current membership end date "
                        "has passed."
                    ),
                })

                # DISABLE ATTENDANCE EMPLOYEE
                employee = partner.attendance_employee_id
                if employee:
                    employee.write({
                        "active": False,
                    })

    # OPEN MEMBER
    def action_open_member(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Member"),
            "res_model": "res.partner",
            "view_mode": "form",
            "res_id": self.member_id.id,
            "target": "current",
        }

    # RENEW MEMBERSHIP
    def action_renew_membership(self):
        # Create a new Sale Order Quotation for renewing this membership.
        self.ensure_one()

        if not self.is_renewable:
            raise ValidationError(
                _(
                    "This membership cannot be renewed. "
                    "It is either not expired or already has "
                    "a renewal order."
                )
            )

        if not self.member_id:
            raise ValidationError(
                _("No member is linked to this membership.")
            )

        if not self.company_id:
            raise ValidationError(
                _("No company is configured for this membership.")
            )

        product_tmpl = self.membership_plan_id.product_id

        if not product_tmpl:
            raise ValidationError(
                _(
                    "No product linked to this membership plan. "
                    "Please configure the plan correctly."
                )
            )

        product_variant = product_tmpl.product_variant_id

        if not product_variant:
            product_variant = product_tmpl.product_variant_ids[:1]

            if not product_variant:
                raise ValidationError(
                    _("No product variant found for this membership plan.")
                )

        # Create renewal quotation in membership company
        sale_order = self.env["sale.order"].with_company(
            self.company_id
        ).create({
            "partner_id": self.member_id.id,
            "company_id": self.company_id.id,
            "user_id": self.env.user.id,
            "origin": self.name,
            "note": _("Renewal of membership %s") % self.name,
        })

        # Create Sale Order Line
        self.env["sale.order.line"].with_company(
            self.company_id
        ).create({
            "order_id": sale_order.id,
            "product_id": product_variant.id,
            "product_template_id": product_tmpl.id,
            "name": product_tmpl.name,
            "product_uom_qty": 1,
            "price_unit": self.membership_plan_id.price,
            "tax_ids": [(6, 0, product_tmpl.taxes_id.ids)],
        })

        self.write({
            "renewal_sale_order_id": sale_order.id,
        })

        return {
            "type": "ir.actions.act_window",
            "name": _("Renewal Quotation"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": sale_order.id,
            "target": "current",
        }