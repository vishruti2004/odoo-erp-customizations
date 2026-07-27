# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    member_code = fields.Char(
        related="member_id.member_code",
        store=True,
        string="Member Code",
    )

    display_member_id = fields.Char(
        string="Member ID",
        compute="_compute_display_member_id",
        store=True,
    )

    renewal_sale_order_id = fields.Many2one(
        "sale.order",
        string="Renewal Order",
        readonly=True,
        help="Sale order created for renewing this membership.",
    )

    is_renewable = fields.Boolean(
        string="Is Renewable",
        compute="_compute_is_renewable",
        store=False,
        help="True if membership is expired and no renewal order exists yet.",
    )

    @api.depends("member_code", "name")
    def _compute_display_member_id(self):
        for rec in self:
            if rec.member_code and rec.name:
                rec.display_member_id = f"{rec.member_code} - {rec.name}"
            else:
                rec.display_member_id = rec.member_code or rec.name or ""

    @api.depends("status", "renewal_sale_order_id")
    def _compute_is_renewable(self):
        """Only expired memberships without an existing renewal order are renewable."""
        for rec in self:
            rec.is_renewable = rec.status == "expired" and not rec.renewal_sale_order_id

    # CREATE / SEQUENCE

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "gym.membership.history"
                )
        return super().create(vals_list)

    # CRON: AUTO EXPIRE

    @api.model
    def _cron_expire_memberships(self):
        """Runs daily to expire memberships whose end date has passed."""
        today = fields.Date.today()
        to_expire = self.search([
            ("status", "=", "active"),
            ("membership_end_date", "<", today),
        ])
        if to_expire:
            to_expire.write({"status": "expired"})

    # ACTION: RENEW MEMBERSHIP

    def action_renew_membership(self):
        """
        Create a new Sale Order Quotation for renewing this membership.
        Button appears only for expired memberships.
        """
        self.ensure_one()

        if not self.is_renewable:
            raise ValidationError(
                _("This membership cannot be renewed. It is either not expired or already has a renewal order.")
            )

        product_tmpl = self.membership_plan_id.product_id
        if not product_tmpl:
            raise ValidationError(
                _("No product linked to this membership plan. Please configure the plan correctly.")
            )

        product_variant = product_tmpl.product_variant_id
        if not product_variant:
            product_variant = product_tmpl.product_variant_ids[:1]
            if not product_variant:
                raise ValidationError(
                    _("No product variant found for this membership plan.")
                )

        sale_order = self.env["sale.order"].create({
            "partner_id": self.member_id.id,
            "company_id": self.env.company.id,
            "user_id": self.env.uid,
            "origin": self.name,
            "note": _("Renewal of membership %s") % self.name,
        })

        self.env["sale.order.line"].create({
            "order_id": sale_order.id,
            "product_id": product_variant.id,
            "product_template_id": product_tmpl.id,
            "name": product_tmpl.name,
            "product_uom_qty": 1,
            "price_unit": product_tmpl.list_price or self.membership_plan_id.price,
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