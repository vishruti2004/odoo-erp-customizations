# -*- coding: utf-8 -*-

from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    membership_plan_id = fields.Many2one("gym.membership.plan", string="Membership Plan", related="partner_id.membership_plan_id", store=True)
    is_membership_expired = fields.Boolean(string="Membership Expired", compute="_compute_is_membership_expired", store=False)

    @api.depends("partner_id.membership_end_date")
    def _compute_is_membership_expired(self):
        """Check if the partner's membership has expired."""
        today = date.today()
        for order in self:
            if order.partner_id.membership_end_date:
                order.is_membership_expired = (
                    order.partner_id.membership_end_date < today
                )
            else:
                order.is_membership_expired = False

    # COMPANY-WISE MEMBER SEQUENCE

    def _get_member_sequence(self, company):
        """Get or create a company-wise sequence for Gym Member IDs."""
        Sequence = self.env["ir.sequence"].sudo()
        sequence = Sequence.search(
            [
                ("code", "=", "gym.member"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )

        if not sequence:
            sequence = Sequence.create(
                {
                    "name": f"Gym Member - {company.name}",
                    "code": "gym.member",
                    "prefix": "GM",
                    "padding": 5,
                    "number_increment": 1,
                    "company_id": company.id,
                }
            )

        return sequence

    def action_confirm(self):
        """Confirm sale order and create membership."""
        MembershipPlan = self.env["gym.membership.plan"]
        MembershipHistory = self.env["gym.membership.history"]

        for order in self:
            partner = order.partner_id
            if partner.company_id and partner.company_id != order.company_id:
                raise ValidationError(
                    _(
                        "The member %s belongs to %s, but this Sale Order belongs to %s."
                    )
                    % (
                        partner.name,
                        partner.company_id.name,
                        order.company_id.name,
                    )
                )

        for order in self:
            partner = order.partner_id
            for line in order.order_line:
                # Find membership plan for the SAME COMPANY
                plan = MembershipPlan.search(
                    [
                        ("product_id", "=", line.product_template_id.id),
                        ("company_id", "=", order.company_id.id),
                    ],
                    limit=1,
                )

                if not plan:
                    continue

                active_membership = MembershipHistory.search(
                    [
                        ("member_id", "=", partner.id),
                        ("company_id", "=", order.company_id.id),
                        ("status", "=", "active"),
                    ],
                    limit=1,
                )

                if active_membership:
                    raise ValidationError(
                        _(
                            "%s already has an active membership. Only one active membership is allowed."
                        )
                        % partner.name
                    )

                break

        res = super().action_confirm()

        for order in self:
            partner = order.partner_id
            for line in order.order_line:
                # Find membership plan for the SAME COMPANY
                plan = MembershipPlan.search(
                    [
                        ("product_id", "=", line.product_template_id.id),
                        ("company_id", "=", order.company_id.id),
                    ],
                    limit=1,
                )

                if not plan:
                    continue

                start_date = fields.Date.context_today(order)

                partner_vals = {
                    "is_gym_member": True,
                    "membership_plan_id": plan.id,
                    "membership_start_date": start_date,
                    "company_id": order.company_id.id,
                }

                # Generate member code only once
                if not partner.member_code:
                    sequence = self._get_member_sequence(order.company_id)
                    partner_vals["member_code"] = sequence.next_by_id()

                partner.write(partner_vals)

                # REACTIVATE ATTENDANCE EMPLOYEE ON RENEWAL

                if partner.attendance_employee_id:
                    employee = partner.attendance_employee_id
                    if not employee.active:
                        employee.write({"active": True})

                MembershipHistory.create(
                    {
                        "member_id": partner.id,
                        "membership_plan_id": plan.id,
                        "membership_start_date": partner.membership_start_date,
                        "membership_end_date": partner.membership_end_date,
                        "status": "active",
                        "remark": "Membership Created",
                    }
                )

                break

        return res

    # RENEW MEMBERSHIP

    def action_renew_membership(self):
        """Create a new renewal quotation from current sale order."""
        self.ensure_one()

        new_order = self.copy(
            {
                "name": "/",
                "state": "draft",
                "date_order": fields.Datetime.now(),
            }
        )

        new_order.message_post(
            body=_("Renewal Quotation created from %s") % self.name
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Renewal Quotation"),
            "res_model": "sale.order",
            "view_mode": "form",
            "res_id": new_order.id,
            "target": "current",
        }


    def action_cancel(self):
        """Reset renewal_sale_order_id when sale order is cancelled."""
        res = super().action_cancel()

        history = self.env["gym.membership.history"].search(
            [("renewal_sale_order_id", "=", self.id)],
            limit=1,
        )

        if history:
            history.renewal_sale_order_id = False

        return res

    def unlink(self):
        """Reset renewal_sale_order_id before deletion."""
        for order in self:
            history = self.env["gym.membership.history"].search(
                [("renewal_sale_order_id", "=", order.id)],
                limit=1,
            )

            if history:
                history.renewal_sale_order_id = False

        return super().unlink()