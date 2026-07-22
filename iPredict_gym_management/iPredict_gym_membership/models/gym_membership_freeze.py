from odoo import fields, models
from odoo.exceptions import ValidationError


class GymMembershipFreeze(models.Model):
    _name = "gym.membership.freeze"
    _description = "Gym Membership Freeze Request"
    _rec_name = "partner_id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    partner_id = fields.Many2one(
        "res.partner",
        string="Member",
        required=True,
    )

    freeze_start_date = fields.Date(
        string="Freeze Start Date",
        required=True,
    )

    freeze_end_date = fields.Date(
        string="Freeze End Date",
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="draft",
        tracking=True,
    )

    def action_submit(self):
        self.ensure_one()

        if not self.freeze_start_date:
            raise ValidationError("Please select Freeze Start Date.")

        if not self.freeze_end_date:
            raise ValidationError("Please select Freeze End Date.")

        if self.freeze_end_date < self.freeze_start_date:
            raise ValidationError(
                "Freeze End Date cannot be earlier than Freeze Start Date."
            )

        template = self.env.ref(
            "iPredict_gym_membership.mail_template_membership_freeze_request",
            raise_if_not_found=False,
        )

        if not template:
            raise ValidationError("Membership Freeze mail template not found.")

        admin_group = self.env.ref("base.group_system")
        admins = admin_group.user_ids.filtered(
            lambda u: u.partner_id.email
        )

        if not admins:
            raise ValidationError(
                "No Administrator found with a valid email address."
            )

        template.send_mail(
            self.partner_id.id,
            email_values={
                "email_to": False,
                "recipient_ids": [(6, 0, admins.mapped("partner_id").ids)],
                "email_from": self.env.company.email_formatted
                or self.env.user.email_formatted,
            },
            force_send=True,
        )

        self.state = "pending"

        return {
            "type": "ir.actions.act_window",
            "name": "Membership Freeze Request",
            "res_model": "gym.membership.freeze",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }

    def action_approve(self):
        self.ensure_one()

        self.partner_id.write({
            "is_frozen": True,
            "freeze_start_date": self.freeze_start_date,
            "freeze_end_date": self.freeze_end_date,
        })

        self.state = "approved"

    def action_reject(self):
        self.ensure_one()

        self.partner_id.write({
            "is_frozen": False,
        })

        self.state = "rejected"