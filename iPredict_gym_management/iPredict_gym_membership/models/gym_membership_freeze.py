# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymMembershipFreeze(models.Model):
    _name = "gym.membership.freeze"
    _description = "Gym Membership Freeze Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    company_id = fields.Many2one("res.company", string="Company", related="partner_id.company_id", store=True, readonly=True, index=True)
    partner_id = fields.Many2one("res.partner", string="Member", required=True, ondelete="cascade", tracking=True, domain="[('is_gym_member', '=', True)]")
    membership_history_id = fields.Many2one("gym.membership.history", string="Active Membership", required=True, tracking=True, domain="[('member_id', '=', partner_id), ('status', '=', 'active')]")
    membership_plan_id = fields.Many2one("gym.membership.plan", string="Membership Plan", related="membership_history_id.membership_plan_id", store=True, readonly=True)
    freeze_start_date = fields.Date(string="Start Date", required=True, tracking=True)
    freeze_end_date = fields.Date(string="End Date", required=True, tracking=True)
    freeze_days = fields.Integer(string="Freeze Days", compute="_compute_freeze_days", store=True)
    membership_extended = fields.Boolean(string="Membership Extended", default=False, copy=False)
    reason = fields.Text(string="Freeze Reason", required=True, tracking=True)
    state = fields.Selection([("draft", "Draft"), ("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], string="Status", default="draft", required=True, tracking=True)

    @api.depends("freeze_start_date", "freeze_end_date")
    def _compute_freeze_days(self):
        for record in self:
            if record.freeze_start_date and record.freeze_end_date:
                record.freeze_days = (
                    record.freeze_end_date - record.freeze_start_date
                ).days + 1
            else:
                record.freeze_days = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get("partner_id")
            membership_history_id = vals.get("membership_history_id")

            if partner_id and membership_history_id:
                history = self.env["gym.membership.history"].browse(
                    membership_history_id
                )
                if history.member_id.id != partner_id or history.status != "active":
                    raise ValidationError(
                        _(
                            "The selected membership must belong to the selected member and must be active."
                        )
                    )
        return super().create(vals_list)

    @api.constrains("partner_id", "membership_history_id")
    def _check_membership(self):
        for record in self:
            if not record.partner_id:
                continue

            if not record.membership_history_id:
                raise ValidationError(_("An active membership is required."))

            if record.membership_history_id.member_id != record.partner_id:
                raise ValidationError(
                    _("The selected membership does not belong to this member.")
                )

            if record.membership_history_id.status != "active":
                raise ValidationError(
                    _("Only an active membership can be frozen.")
                )

    @api.constrains("freeze_start_date", "freeze_end_date")
    def _check_dates(self):
        for record in self:
            if (
                record.freeze_start_date
                and record.freeze_end_date
                and record.freeze_end_date < record.freeze_start_date
            ):
                raise ValidationError(
                    _(
                        "Freeze End Date must be greater than or equal to Freeze Start Date."
                    )
                )

            if (
                record.partner_id
                and record.partner_id.membership_end_date
                and record.freeze_start_date
                and record.freeze_start_date
                > record.partner_id.membership_end_date
            ):
                raise ValidationError(
                    _(
                        "Freeze Start Date cannot be after the member's membership End Date."
                    )
                )

    @api.constrains(
        "partner_id",
        "membership_history_id",
        "freeze_start_date",
        "freeze_end_date",
        "state",
    )
    def _check_overlap(self):
        for record in self:
            if (
                not record.partner_id
                or not record.membership_history_id
                or not record.freeze_start_date
                or not record.freeze_end_date
                or record.state == "rejected"
            ):
                continue

            overlapping = self.search(
                [
                    ("id", "!=", record.id),
                    ("partner_id", "=", record.partner_id.id),
                    (
                        "membership_history_id",
                        "=",
                        record.membership_history_id.id,
                    ),
                    ("state", "in", ["draft", "pending", "approved"]),
                    ("freeze_start_date", "<=", record.freeze_end_date),
                    ("freeze_end_date", ">=", record.freeze_start_date),
                ],
                limit=1,
            )
            if overlapping:
                raise ValidationError(
                    _(
                        "A freeze request already exists for this membership during the selected period."
                    )
                )

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise ValidationError(
                _("Only draft freeze requests can be submitted.")
            )

        if not self.reason or not self.reason.strip():
            raise ValidationError(_("Please provide a freeze reason."))

        if (
            not self.membership_history_id
            or self.membership_history_id.status != "active"
        ):
            raise ValidationError(
                _("An active membership is required to submit a freeze request.")
            )

        self.state = "pending"

        trainer_partners = self.partner_id.trainer_id.mapped(
            "user_id.partner_id"
        )
        admin_group = self.env.ref(
            "iPredict_gym_base.group_gym_admin", raise_if_not_found=False
        )

        admin_partners = self.env["res.partner"]
        if admin_group:
            admin_users = admin_group.all_user_ids.filtered(
                lambda u: (
                    u.company_id == self.company_id
                    or self.company_id in u.company_ids
                )
            )
            admin_partners = admin_users.mapped("partner_id")

        recipients = (trainer_partners | admin_partners).filtered(
            lambda p: p.email
        )

        if recipients:
            template = self.env.ref(
                "iPredict_gym_membership.mail_template_membership_freeze_request",
                raise_if_not_found=False,
            )
            if template:
                template.send_mail(
                    self.id,
                    force_send=True,
                    email_values={
                        "email_to": ",".join(recipients.mapped("email")),
                    },
                )
        return True

    def _check_approval_access(self):
        self.ensure_one()
        user = self.env.user
        if user.has_group("iPredict_gym_base.group_gym_admin"):
            return True

        trainers = self.partner_id.trainer_id
        if any(t.user_id == user for t in trainers):
            return True

        raise ValidationError(
            _(
                "Only the assigned trainer or Gym Administrator can approve or reject this request."
            )
        )

    def action_approve(self):
        self.ensure_one()
        self._check_approval_access()

        if self.state != "pending":
            raise ValidationError(
                _("Only pending freeze requests can be approved.")
            )

        partner = self.partner_id
        if not partner.membership_start_date or not partner.membership_end_date:
            raise ValidationError(
                _(
                    "The member does not have valid Membership Start or End Date."
                )
            )

        self.state = "approved"

        today = fields.Date.today()
        if (
            self.freeze_start_date
            and self.freeze_start_date <= today
            and self.freeze_end_date
            and self.freeze_end_date >= today
        ):
            self._apply_freeze()

        return True

    def action_reject(self):
        self.ensure_one()
        self._check_approval_access()

        if self.state != "pending":
            raise ValidationError(
                _("Only pending freeze requests can be rejected.")
            )

        self.state = "rejected"
        return True

    def _apply_freeze(self):
        self.ensure_one()
        if self.state != "approved":
            return

        partner = self.partner_id
        today = fields.Date.today()

        if not partner or not partner.membership_start_date or not partner.membership_end_date:
            return

        if not self.freeze_start_date or not self.freeze_end_date:
            return

        if not (self.freeze_start_date <= today <= self.freeze_end_date):
            return

        if partner.is_frozen or self.freeze_days <= 0:
            return

        if not self.membership_extended:
            partner.write(
                {
                    "membership_freeze_extension_days": (
                        partner.membership_freeze_extension_days
                        + self.freeze_days
                    ),
                }
            )
            self.membership_extended = True

        membership = self.membership_history_id
        if membership and membership.status == "active":
            membership.write(
                {
                    "status": "frozen",
                    "remark": _(
                        "Membership frozen from %s to %s. Reason: %s"
                    )
                    % (
                        self.freeze_start_date,
                        self.freeze_end_date,
                        self.reason or "",
                    ),
                }
            )

        partner.write(
            {
                "is_frozen": True,
                "freeze_start_date": self.freeze_start_date,
                "freeze_end_date": self.freeze_end_date,
            }
        )

    def _apply_resume(self):
        self.ensure_one()
        partner = self.partner_id
        if not partner:
            return

        membership = self.membership_history_id
        if membership and membership.status == "frozen":
            membership.write(
                {
                    "status": "active",
                    "remark": _("Membership freeze completed."),
                }
            )

        partner.write(
            {
                "is_frozen": False,
                "freeze_start_date": False,
                "freeze_end_date": False,
            }
        )

    @api.model
    def _cron_apply_freeze_schedule(self):
        today = fields.Date.today()

        freeze_requests = self.search(
            [
                ("state", "=", "approved"),
                ("freeze_start_date", "<=", today),
                ("freeze_end_date", ">=", today),
            ]
        )
        for request in freeze_requests:
            partner = request.partner_id
            if (
                partner
                and partner.membership_start_date
                and partner.membership_end_date
                and (partner.membership_start_date <= today <= partner.membership_end_date)
            ):
                request._apply_freeze()

        completed_requests = self.search(
            [
                ("state", "=", "approved"),
                ("freeze_end_date", "<", today),
            ]
        )
        for request in completed_requests:
            request._apply_resume()