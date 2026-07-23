# -*- coding: utf-8 -*-

from odoo import fields, models, api


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        res = super().action_confirm()

        MembershipPlan = self.env["gym.membership.plan"]
        MembershipHistory = self.env["gym.membership.history"]

        for order in self:
            partner = order.partner_id

            for line in order.order_line:
                plan = MembershipPlan.search(
                    [("product_id", "=", line.product_template_id.id)],
                    limit=1,
                )

                if not plan:
                    continue

                start_date = fields.Date.context_today(order)

                partner_vals = {
                    "is_gym_member": True,
                    "membership_plan_id": plan.id,
                    "membership_start_date": start_date,
                }

                if not partner.member_code:
                    partner_vals["member_code"] = self.env["ir.sequence"].next_by_code(
                        "gym.member"
                    )

                partner.write(partner_vals)

                # Create membership history
                MembershipHistory.create({
                    "member_id": partner.id,
                    "membership_plan_id": plan.id,
                    "membership_start_date": partner.membership_start_date,
                    "membership_end_date": partner.membership_end_date,
                    "status": "active",
                    "remark": "Membership Created",
                })

                break

        return res