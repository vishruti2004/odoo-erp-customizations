from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

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

    membership_history_id = fields.Many2one(
        "gym.membership.history",
        string="Active Membership",
        required=True,
        domain="[('member_id', '=', partner_id), ('status', '=', 'active')]",
        help="Select the active membership plan that should be frozen.",
    )

    freeze_start_date = fields.Date(
        string="Start Date",
        required=True,
    )

    freeze_end_date = fields.Date(
        string="End Date",
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

    # VALIDATIONS

    @api.constrains("freeze_start_date", "freeze_end_date")
    def _check_dates_order(self):
        for rec in self:
            if rec.freeze_start_date and rec.freeze_end_date:
                if rec.freeze_end_date < rec.freeze_start_date:
                    raise ValidationError(
                        _("Freeze End Date cannot be earlier than Freeze Start Date.")
                    )

    @api.constrains("freeze_start_date", "freeze_end_date")
    def _check_dates_not_in_past(self):
        today = fields.Date.today()
        for rec in self:
            if rec.freeze_start_date and rec.freeze_start_date < today:
                raise ValidationError(
                    _("Freeze Start Date cannot be a past date.")
                )
            if rec.freeze_end_date and rec.freeze_end_date < today:
                raise ValidationError(
                    _("Freeze End Date cannot be a past date.")
                )

    @api.constrains("freeze_start_date", "freeze_end_date", "membership_history_id")
    def _check_dates_within_membership(self):
        for rec in self:
            if not rec.membership_history_id:
                continue
            m_start = rec.membership_history_id.membership_start_date
            m_end = rec.membership_history_id.membership_end_date

            if rec.freeze_start_date and m_start and rec.freeze_start_date < m_start:
                raise ValidationError(
                    _("Freeze Start Date cannot be before the Membership Start Date (%s).")
                    % m_start
                )

            if rec.freeze_end_date and m_end and rec.freeze_end_date > m_end:
                raise ValidationError(
                    _("Freeze End Date cannot be after the Membership End Date (%s).")
                    % m_end
                )

    @api.constrains("freeze_start_date", "freeze_end_date", "membership_history_id", "state")
    def _check_no_overlap(self):
        for rec in self:
            if not (rec.membership_history_id and rec.freeze_start_date and rec.freeze_end_date):
                continue
            if rec.state == "rejected":
                continue

            domain = [
                ("id", "!=", rec.id),
                ("membership_history_id", "=", rec.membership_history_id.id),
                ("state", "!=", "rejected"),
                ("freeze_start_date", "<=", rec.freeze_end_date),
                ("freeze_end_date", ">=", rec.freeze_start_date),
            ]
            overlapping = self.search_count(domain)
            if overlapping:
                raise ValidationError(
                    _("This membership already has an overlapping freeze request "
                      "for the selected dates. Please check existing freeze requests "
                      "before creating a new one.")
                )

    
    # ACTIONS

    def action_submit(self):
        self.ensure_one()

        if not self.membership_history_id:
            raise ValidationError(_("Please select the Active Membership to freeze."))

        if not self.freeze_start_date:
            raise ValidationError(_("Please select Freeze Start Date."))

        if not self.freeze_end_date:
            raise ValidationError(_("Please select Freeze End Date."))

        template = self.env.ref(
            "iPredict_gym_membership.mail_template_membership_freeze_request",
            raise_if_not_found=False,
        )

        if not template:
            raise ValidationError(_("Membership Freeze mail template not found."))

        admin_group = self.env.ref("base.group_system")
        recipients = admin_group.user_ids.filtered(lambda u: u.partner_id.email)

   

        if not recipients:
            raise ValidationError(
                _("No Administrator found with a valid email address.")
            )

        template.send_mail(
            self.id,
            email_values={
                "email_to": False,
                "recipient_ids": [(6, 0, recipients.mapped("partner_id").ids)],
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
        self.state = "approved"

        today = fields.Date.today()
        if self.freeze_start_date and self.freeze_start_date <= today:
            self._apply_freeze()

    def action_reject(self):
        self.ensure_one()

        self.partner_id.write({
            "is_frozen": False,
        })

        self.state = "rejected"

    def _apply_freeze(self):
        self.ensure_one()
        self.partner_id.write({
            "is_frozen": True,
            "freeze_start_date": self.freeze_start_date,
            "freeze_end_date": self.freeze_end_date,
        })
        if self.membership_history_id and self.membership_history_id.status == "active":
            freeze_days = (self.freeze_end_date - self.freeze_start_date).days + 1

            history = self.membership_history_id
            if history.membership_end_date:
                history.membership_end_date = history.membership_end_date + timedelta(
                    days=freeze_days
                )

            history.status = "frozen"

    def _apply_resume(self):
        self.ensure_one()
        self.partner_id.write({
            "is_frozen": False,
        })
        if self.membership_history_id and self.membership_history_id.status == "frozen":
            self.membership_history_id.status = "active"

    # DAILY AUTOMATIC FREEZE / RESUME SWITCH 

    @api.model
    def _cron_apply_freeze_schedule(self):
        _logger = logging.getLogger(__name__)
        _logger.info("=== CRON: Freeze Schedule Started ===")
        
        today = fields.Date.today()
        _logger.info("Today: %s", today)
        
        to_freeze = self.search([
            ("state", "=", "approved"),
            ("freeze_start_date", "<=", today),
            ("freeze_end_date", ">=", today),
        ])
        _logger.info("Found %s requests to freeze", len(to_freeze))
        
        for rec in to_freeze:
            _logger.info("Freezing: %s (Start: %s, End: %s)", 
                        rec.partner_id.name, 
                        rec.freeze_start_date, 
                        rec.freeze_end_date)
            rec._apply_freeze()
        
        to_resume = self.search([
            ("state", "=", "approved"),
            ("freeze_end_date", "<", today),
        ])
        _logger.info("Found %s requests to resume", len(to_resume))
        
        for rec in to_resume:
            _logger.info("Resuming: %s", rec.partner_id.name)
            rec._apply_resume()
        
        _logger.info("=== CRON: Freeze Schedule Finished ===")