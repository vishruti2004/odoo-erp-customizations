import logging

from odoo import _, api, fields, models, Command
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

LIVE_STATES = ("draft", "allocated", "renewal_pending", "expired")


class LockerAllocation(models.Model):
    _name = "locker.allocation"
    _description = "Locker Allocation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "id desc"

    # FIELDS
    name = fields.Char(string="Allocation Number", required=True, copy=False, readonly=True, default="New", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, tracking=True)
    locker_id = fields.Many2one("locker.locker", string="Locker", required=True, ondelete="restrict", tracking=True, domain="[('status', '=', 'available'), ('company_id', '=', company_id)]")
    partner_id = fields.Many2one("res.partner", string="Partner", required=True, tracking=True, ondelete="restrict")
    start_date = fields.Date(string="Start Date", required=True, default=fields.Date.context_today, tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    state = fields.Selection([("draft", "Draft"), ("allocated", "Allocated"), ("renewal_pending", "Renewal Pending"), ("expired", "Expired"), ("returned", "Returned"), ("cancelled", "Cancelled")], default="draft", tracking=True, copy=False)
    note = fields.Html()
    profile_id = fields.Many2one("locker.profile", related="locker_id.profile_id", readonly=True)
    access_method = fields.Selection(related="profile_id.access_method", string="Access Method", store=True, readonly=True)
    allocation_type = fields.Selection(related="locker_id.profile_id.allocation_type", string="Allocation Type", store=True, readonly=True)
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True, copy=False, tracking=True)
    payment_state = fields.Selection(related="invoice_id.payment_state", string="Payment Status", readonly=True)
    invoice_count = fields.Integer(compute="_compute_invoice_count")
    renewal_available = fields.Boolean(string="Renewal Available", default=False, copy=False)
    renewal_invoice_id = fields.Many2one("account.move", string="Renewal Invoice", readonly=True, copy=False, tracking=True, help="Open renewal invoice of the current renewal. It is cleared when the renewal is completed.")
    authorized_partner_ids = fields.Many2many("res.partner", string="Authorized Persons", tracking=True)
    credential_ids = fields.One2many("locker.access.credential", "allocation_id", string="Authentication Credentials", copy=False)
    pin_code = fields.Char(string="Locker PIN", copy=False, readonly=True, tracking=True)
    qr_token = fields.Char(string="QR Token", copy=False, readonly=True, tracking=True)
    rfid_uid = fields.Char(string="RFID UID", copy=False, tracking=True)
    biometric_id = fields.Char(string="Biometric ID", copy=False, tracking=True)
    return_reason_id = fields.Many2one("locker.return.reason", string="Return Reason", readonly=True, copy=False, tracking=True)
    return_date = fields.Date(string="Return Date", readonly=True, copy=False)
    reserved_until = fields.Datetime(string="Reserved Until", readonly=True, copy=False, tracking=True, help="The locker stays reserved for this allocation until this time. After that the reservation is released automatically.")

    # PENALTY FIELDS
    penalty_available = fields.Boolean(string="Penalty Available", default=False, copy=False, tracking=True)
    penalty_start_date = fields.Date(string="Penalty Start Date", readonly=True, copy=False, tracking=True)
    penalty_invoice_id = fields.Many2one("account.move", string="Penalty Invoice", readonly=True, copy=False, tracking=True)
    penalty_invoice_count = fields.Integer(string="Penalty Invoice Count", compute="_compute_penalty_invoice_count")
    penalty_payment_state = fields.Selection(related="penalty_invoice_id.payment_state", string="Penalty Payment Status", readonly=True)
    penalty_id = fields.Many2one(
        "locker.penalty",
        string="Penalty",
        readonly=True,
        copy=False,
        tracking=True,
    )
    penalty_days = fields.Integer(
        string="Penalty Days",
        readonly=True,
        copy=False,
    )
    penalty_amount = fields.Monetary(
        string="Penalty Amount",
        readonly=True,
        copy=False,
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )
    def _post_history(self, title, details=None):
        for record in self:
            message = title
            if details:
                message += "\n" + "\n".join(f"{label}: {value}" for label, value in details if value not in (False, None, ""))
            record.message_post(body=message)

    # COMPUTE METHODS
    @api.depends("invoice_id")
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = 1 if rec.invoice_id else 0

    @api.depends("penalty_invoice_id")
    def _compute_penalty_invoice_count(self):
        for rec in self:
            rec.penalty_invoice_count = 1 if rec.penalty_invoice_id else 0

    # CREATE / WRITE
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(self._prepare_create_vals(vals_list))
        for record in records:
            if record.state == "draft":
                record._reserve_locker()
            record._sync_access_credentials()
        return records

    # RESERVATION
    @api.constrains("locker_id", "state")
    def _check_locker_single_live_allocation(self):
        for rec in self:
            if not rec.locker_id or rec.state not in LIVE_STATES:
                continue
            other = self.sudo().search([
                ("id", "!=", rec.id),
                ("locker_id", "=", rec.locker_id.id),
                ("state", "in", LIVE_STATES),
            ], limit=1)
            if other:
                raise ValidationError(
                    _("Locker '%(locker)s' is already %(status)s for '%(partner)s' (%(allocation)s).")
                    % {
                        "locker": rec.locker_id.display_name,
                        "status": _("reserved") if other.state == "draft" else _("allocated"),
                        "partner": other.partner_id.display_name,
                        "allocation": other.name,
                    }
                )

    def _reserve_locker(self):
        for rec in self:
            locker = rec.locker_id.sudo()
            if locker.status == "allocated":
                raise ValidationError(
                    _("Locker '%s' is already allocated.") % locker.display_name
                )
            hours = rec.company_id.locker_reservation_hours or 0
            vals = {}
            if hours > 0:
                vals["reserved_until"] = fields.Datetime.now() + relativedelta(hours=hours)
            if vals:
                rec.sudo().write(vals)
            if locker.status == "available":
                locker.status = "reserved"

    def _release_locker(self, locker=None):
        """Put a reserved locker back to available."""
        for rec in self:
            locker_to_release = (locker or rec.locker_id).sudo()
            if locker_to_release.status == "reserved":
                locker_to_release.status = "available"

    def _prepare_create_vals(self, vals_list):
        Sequence = self.env["ir.sequence"]

        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id

            if vals.get("name", "New") == "New":
                company = self.env["res.company"].browse(company_id)

                sequence_code = f"locker.allocation.{company_id}"

                sequence = Sequence.search(
                    [
                        ("code", "=", sequence_code),
                        ("company_id", "=", company_id),
                    ],
                    limit=1,
                )

                if not sequence:
                    sequence = Sequence.create({
                        "name": f"Locker Allocation - {company.name}",
                        "code": sequence_code,
                        "company_id": company_id,
                        "prefix": "LA/%(year)s/",
                        "padding": 5,
                        "number_increment": 1,
                        "use_date_range": True,
                    })

                vals["name"] = sequence.next_by_id()

        return vals_list

    def write(self, vals):
        for allocation in self:
            if allocation.state not in ("renewal_pending", "expired"):
                vals["renewal_available"] = False
                break
        old_lockers = {rec.id: rec.locker_id for rec in self} if "locker_id" in vals else {}
        result = super().write(vals)
        if "locker_id" in vals:
            for rec in self:
                old_locker = old_lockers.get(rec.id)
                if old_locker and old_locker != rec.locker_id:
                    rec._release_locker(old_locker)
                if rec.state == "draft":
                    rec._reserve_locker()
        if any(field in vals for field in ("partner_id", "authorized_partner_ids", "locker_id")):
            self._sync_access_credentials()
        return result

    def unlink(self):
        reserved_lockers = self.filtered(lambda a: a.state == "draft").mapped("locker_id")
        result = super().unlink()
        for locker in reserved_lockers:
            if locker.status == "reserved":
                locker.sudo().status = "available"
        return result

    # CREDENTIAL SYNC
    def _sync_access_credentials(self):
        Credential = self.env["locker.access.credential"].sudo()
        for allocation in self:
            if not allocation.id:
                continue
            partner_ids = set()
            if allocation.partner_id:
                partner_ids.add(allocation.partner_id.id)
            partner_ids.update(allocation.authorized_partner_ids.ids)
            # Create or reactivate credentials
            for partner_id in partner_ids:
                credential = Credential.search([("allocation_id", "=", allocation.id), ("partner_id", "=", partner_id)], limit=1)
                if not credential:
                    credential = Credential.create({"allocation_id": allocation.id, "partner_id": partner_id, "active": True})
                else:
                    credential.active = True
                access_method = allocation.access_method
                if access_method in ("pin", "rfid", "qr"):
                    has_value = (
                        bool(credential.pin_code) if access_method == "pin"
                        else (bool(credential.rfid_uid) if access_method == "rfid" else bool(credential.qr_token and credential.qr_code))
                    )
                    if not has_value:
                        credential.action_generate_credential()
                elif access_method in ("physical_key", "biometric"):
                    if credential.pin_code or credential.rfid_uid or credential.qr_token or credential.qr_code:
                        credential.action_clear_credential()
            # Deactivate removed partners
            all_credentials = Credential.search([("allocation_id", "=", allocation.id)])
            for cred in all_credentials:
                if cred.partner_id.id not in partner_ids:
                    cred.active = False

    def action_create_invoice(self):
        self.ensure_one()
        if self.allocation_type != "paid":
            raise ValidationError(_("Invoice is not required for Free Locker."))
        if self.invoice_id:
            raise ValidationError(_("Invoice already exists."))
        product = self.profile_id.rental_product_id
        if not product:
            raise ValidationError(_("Please configure Rental Product in Locker Profile."))
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": self.name,
            "invoice_line_ids": [Command.create({"product_id": product.id, "name": product.display_name, "quantity": 1, "price_unit": product.lst_price})],
        })
        self.invoice_id = invoice.id
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": invoice.id, "view_mode": "form", "target": "current"}

    def action_view_invoice(self):
        self.ensure_one()
        if not self.invoice_id:
            raise ValidationError(_("No invoice found."))
        return {"type": "ir.actions.act_window", "res_model": "account.move", "view_mode": "form", "res_id": self.invoice_id.id}

    # PENALTY
    def action_create_penalty(self):
        self.ensure_one()
        penalty = self.env["locker.penalty"].search([
            ("company_id", "=", self.company_id.id),
            ("active", "=", True),
        ], order="id desc", limit=1)

        if not penalty:
            raise ValidationError(_("Please configure an active Locker Penalty."))

        if not penalty.amount or penalty.amount <= 0:
            raise ValidationError(_("Please configure a valid Penalty Amount."))

        if self.state != "expired":
            raise ValidationError(
                _("Penalty can only be created for an expired allocation.")
            )

        if not self.penalty_available:
            raise ValidationError(_("Penalty is not available yet."))

        if self.penalty_invoice_id:
            raise ValidationError(_("Penalty invoice already exists."))

        if not self.penalty_start_date:
            raise ValidationError(_("Penalty Start Date is not configured."))

        today = fields.Date.context_today(self)
        if today < self.penalty_start_date:
            raise ValidationError(_("Penalty is not available yet."))

        if not self.profile_id.rental_product_id:
            raise ValidationError(
                _("Please configure Rental Product in Locker Profile.")
            )

        invoice = self._create_penalty_invoice(penalty, today)

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    def _compute_penalty_amount(self, penalty, today):
        """Return (penalty_days, penalty_amount) from the penalty start date until today."""
        self.ensure_one()
        penalty_days = (today - self.penalty_start_date).days

        if penalty.period == "day":
            penalty_amount = penalty.amount * penalty_days

        elif penalty.period == "month":
            penalty_amount = 0.0
            current_date = self.penalty_start_date

            for day_index in range(penalty_days):
                next_month = current_date + relativedelta(months=1)
                month_start = next_month.replace(day=1)
                last_day = month_start - relativedelta(days=1)
                days_in_month = last_day.day
                penalty_amount += penalty.amount / days_in_month
                current_date += relativedelta(days=1)

        else:
            penalty_amount = 0.0
            current_date = self.penalty_start_date

            for day_index in range(penalty_days):
                next_year = current_date + relativedelta(years=1)
                days_in_year = (next_year - current_date).days
                penalty_amount += penalty.amount / days_in_year
                current_date += relativedelta(days=1)

        return penalty_days, penalty_amount

    def _get_penalty_line_name(self, penalty, today, penalty_days):
        product = self.profile_id.rental_product_id
        period_labels = {
            "day": _("Day"),
            "month": _("Month"),
            "year": _("Year"),
        }
        period_label = period_labels.get(penalty.period, _("Penalty"))
        return (
            f"{product.display_name} - Penalty ({period_label})\n"
            f"{self.penalty_start_date.strftime('%d/%m/%Y')} to "
            f"{today.strftime('%d/%m/%Y')} - {penalty_days} Days"
        ), period_label

    def _create_penalty_invoice(self, penalty, today):
        """Create the (draft) penalty invoice for the current expired allocation."""
        self.ensure_one()
        product = self.profile_id.rental_product_id
        penalty_days, penalty_amount = self._compute_penalty_amount(penalty, today)
        line_name, period_label = self._get_penalty_line_name(penalty, today, penalty_days)

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": f"{self.name} - Penalty",
            "invoice_date": today,
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                "name": line_name,
                "quantity": 1,
                "price_unit": penalty_amount,
            })],
        })
        invoice.action_post()

        self.write({
            "penalty_id": penalty.id,
            "penalty_days": penalty_days,
            "penalty_amount": penalty_amount,
            "penalty_invoice_id": invoice.id,
            "penalty_available": False,
        })

        self._post_history(_("Locker Penalty Invoice Created"), [
            ("Locker", self.locker_id.display_name),
            ("Partner", self.partner_id.display_name),
            ("Penalty Invoice", invoice.name),
            ("Penalty Amount", penalty_amount),
            ("Penalty Period", period_label),
            ("Penalty Days", penalty_days),
            ("Penalty Start Date", self.penalty_start_date),
            ("Created By", self.env.user.name),
        ])
        self._send_penalty_notification()
        return invoice

    def _get_penalty_payment_link(self):
        self.ensure_one()
        invoice = self.penalty_invoice_id.sudo()
        if not invoice:
            return False
        return invoice.get_base_url() + invoice._get_share_url()

    def _send_penalty_notification(self):
        """Mail the person the penalty details with the invoice payment link."""
        for rec in self:
            if not rec.penalty_invoice_id:
                continue
            rec._send_state_notification(
                "iPredict_locker_management.mail_template_locker_penalty",
                extra_ctx={"payment_link": rec._get_penalty_payment_link()},
            )

    def _auto_create_penalty(self, penalty, today):
        self.ensure_one()
        if not self.profile_id.rental_product_id or not penalty.amount or penalty.amount <= 0:
            return False
        _days, amount = self._compute_penalty_amount(penalty, today)
        if amount <= 0:
            # Penalty has not accrued yet (e.g. first day); try again on the next run.
            return False
        try:
            with self.env.cr.savepoint():
                self._create_penalty_invoice(penalty, today)
        except Exception:
            _logger.exception("Unable to create penalty invoice automatically for %s", self.name)
            return False
        return True

    def _auto_update_draft_penalty(self, penalty, today):
        self.ensure_one()
        invoice = self.penalty_invoice_id
        if not invoice or invoice.state != "draft" or not self.penalty_start_date:
            return False
        penalty_days, penalty_amount = self._compute_penalty_amount(penalty, today)
        if penalty_days == self.penalty_days and penalty_amount == self.penalty_amount:
            return False
        line = invoice.invoice_line_ids[:1]
        if not line:
            return False
        try:
            with self.env.cr.savepoint():
                line_name, _label = self._get_penalty_line_name(penalty, today, penalty_days)
                line.write({"price_unit": penalty_amount, "name": line_name})
                self.write({"penalty_days": penalty_days, "penalty_amount": penalty_amount})
        except Exception:
            _logger.exception("Unable to update penalty invoice for %s", self.name)
            return False
        return True

    def action_view_penalty_invoice(self):
        self.ensure_one()
        if not self.penalty_invoice_id:
            raise ValidationError(_("No penalty invoice found."))
        return {"type": "ir.actions.act_window", "res_model": "account.move", "view_mode": "form", "res_id": self.penalty_invoice_id.id, "target": "current"}

    # ALLOCATE
    def action_allocate(self):
        for rec in self:
            if not rec.locker_id:
                raise ValidationError(_("Please select a locker."))
            if not rec.partner_id:
                raise ValidationError(_("Please select a partner."))
            if not rec.profile_id:
                raise ValidationError(_("The selected locker does not have a Locker Profile."))
            if rec.allocation_type == "paid":
                if not rec.invoice_id:
                    raise ValidationError(_("Please create the invoice first."))
                if rec.invoice_id.state != "posted":
                    raise ValidationError(_("Please post the invoice first."))
                if rec.invoice_id.payment_state != "paid":
                    raise ValidationError(_("Please register the payment before allocating."))
            existing = self.search([("id", "!=", rec.id), ("locker_id", "=", rec.locker_id.id), ("state", "=", "allocated")], limit=1)
            if existing:
                raise ValidationError(_("Locker '%s' is already allocated to '%s'.") % (rec.locker_id.display_name, existing.partner_id.display_name))
            rec._sync_access_credentials()
            rec.state = "allocated"
            rec.reserved_until = False
            rec.locker_id.sudo().status = "allocated"
            rec._post_history(_("Locker Allocated"), [
                ("Locker", rec.locker_id.display_name),
                ("Allocated To", rec.partner_id.display_name),
                ("Start Date", rec.start_date),
                ("End Date", rec.end_date),
                ("Allocated By", self.env.user.name),
            ])

    def _allocate_from_paid_invoice(self):
        """Draft allocation whose invoice is paid -> Allocated automatically."""
        for rec in self:
            invoice = rec.invoice_id
            if (rec.state != "draft" or rec.allocation_type != "paid"
                    or not invoice or invoice.payment_state != "paid"):
                continue
            try:
                with self.env.cr.savepoint():
                    rec.action_allocate()
            except Exception:
                _logger.exception("Unable to auto-allocate %s after payment", rec.name)

    # RETURN
    def action_return(self):
        self.ensure_one()
        if self.state not in ("allocated", "renewal_pending", "expired"):
            raise ValidationError(_("Locker return is not allowed in current state."))

        self._check_user_can_return()

        if self.penalty_invoice_id and self.penalty_invoice_id.sudo().payment_state != "paid":
            raise ValidationError(
                _("Locker cannot be returned until the penalty invoice is fully paid.")
            )

        return {
            "type": "ir.actions.act_window",
            "name": _("Return Locker"),
            "res_model": "locker.return.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_allocation_id": self.id,
                "default_locker_id": self.locker_id.id,
            },
        }

    def _check_user_can_return(self):
        """A locker user can only return his own locker; an administrator can return any."""
        self.ensure_one()
        if self.env.user.has_group("iPredict_locker_management.group_locker_admin"):
            return
        if self.partner_id != self.env.user.partner_id:
            raise ValidationError(_("Only the locker owner can return this locker."))

    # RENEWAL AUTOMATION + PENALTY CRON
    @api.model
    def _cron_update_renewal_availability(self):
        today = fields.Date.context_today(self)

        _logger.warning(
            "[LOCKER CRON] STARTED | Date: %s",
            today,
        )

        allocations = self.search([
            ("state", "in", ("allocated", "renewal_pending", "expired")),
            ("end_date", "!=", False),
        ])

        _logger.warning(
            "[LOCKER CRON] Allocations found: %s",
            len(allocations),
        )

        for rec in allocations:
            company = rec.company_id

            reminder_days = company.renewal_reminder_days or 0
            renewal_date = rec.end_date - relativedelta(days=reminder_days)
            old_state = rec.state

            if today >= rec.end_date:
                new_state = "expired"
                renewal_available = True
            elif today >= renewal_date:
                new_state = "renewal_pending"
                renewal_available = True
            else:
                new_state = "allocated"
                renewal_available = False

            _logger.warning(
                "[LOCKER CRON CHECK] Allocation: %s | Old: %s | "
                "New: %s | End Date: %s | Renewal Date: %s",
                rec.name,
                old_state,
                new_state,
                rec.end_date,
                renewal_date,
            )

            if old_state != new_state:
                _logger.warning(
                    "[LOCKER STATE CHANGE] %s: %s -> %s",
                    rec.name,
                    old_state,
                    new_state,
                )

                rec.state = new_state
                rec.renewal_available = renewal_available

                if new_state == "renewal_pending":
                    rec._post_history(_("Locker Renewal Pending"), [
                        ("Locker", rec.locker_id.display_name),
                        ("Partner", rec.partner_id.display_name),
                        ("End Date", rec.end_date),
                        ("Renewal Reminder Date", renewal_date),
                    ])

                    _logger.warning(
                        "[LOCKER MAIL] Calling renewal-pending email | "
                        "Allocation: %s | Email: %s",
                        rec.name,
                        rec.partner_id.email,
                    )

                    rec._send_state_notification(
                        "iPredict_locker_management.mail_template_locker_renewal_pending"
                    )

                    _logger.warning(
                        "[LOCKER MAIL] Renewal-pending email function completed | %s",
                        rec.name,
                    )

                elif new_state == "expired":
                    rec._post_history(_("Locker Expired"), [
                        ("Locker", rec.locker_id.display_name),
                        ("Partner", rec.partner_id.display_name),
                        ("End Date", rec.end_date),
                        ("Expired On", today),
                    ])

                    _logger.warning(
                        "[LOCKER MAIL] Calling expired email | "
                        "Allocation: %s | Email: %s",
                        rec.name,
                        rec.partner_id.email,
                    )

                    rec._send_state_notification(
                        "iPredict_locker_management.mail_template_locker_expired"
                    )

                    _logger.warning(
                        "[LOCKER MAIL] Expired email function completed | %s",
                        rec.name,
                    )

            else:
                _logger.warning(
                    "[LOCKER CRON] No state change for allocation %s",
                    rec.name,
                )

            # PENALTY LOGIC — unchanged
            penalty = self.env["locker.penalty"].search([
                ("company_id", "=", company.id),
                ("active", "=", True),
            ], order="id desc", limit=1)

            if not penalty:
                rec.write({
                    "penalty_available": False,
                    "penalty_start_date": False,
                })
                continue

            if rec.state != "expired":
                rec.penalty_available = False
                continue

            if rec.penalty_invoice_id:
                rec.penalty_available = False
                rec._auto_update_draft_penalty(penalty, today)
                continue

            penalty_start_date = rec.end_date + relativedelta(
                days=penalty.start_after_days or 0
            )

            rec.penalty_start_date = penalty_start_date
            rec.penalty_available = today >= penalty_start_date

            if rec.penalty_available:
                rec._auto_create_penalty(penalty, today)

        self._complete_paid_renewals()
        self.search([
            ("state", "=", "draft"),
            ("invoice_id", "!=", False),
        ])._allocate_from_paid_invoice()

        self.search([
            ("state", "in", ("draft", "returned", "cancelled")),
            ("renewal_available", "=", True),
        ]).write({"renewal_available": False})

        _logger.warning("[LOCKER CRON] FINISHED")

    def _send_state_notification(self, template_xmlid, extra_ctx=None):
        _logger.warning(
            "[LOCKER MAIL] Notification function called | Template: %s | Allocation IDs: %s",
            template_xmlid,
            self.ids,
        )

        template = self.env.ref(template_xmlid, raise_if_not_found=False)

        if not template:
            _logger.error("[LOCKER MAIL] TEMPLATE NOT FOUND: %s", template_xmlid)
            return

        _logger.warning("[LOCKER MAIL] Template found: %s", template.display_name)

        for rec in self:
            email = (rec.partner_id.email or "").strip()

            _logger.warning(
                "[LOCKER MAIL] Allocation: %s | State: %s | Partner: %s | Email available: %s",
                rec.name,
                rec.state,
                rec.partner_id.display_name,
                bool(email),
            )

            if not email:
                _logger.error(
                    "[LOCKER MAIL] Email missing for allocation %s",
                    rec.name,
                )
                continue

            try:
                with self.env.cr.savepoint():
                    mail_id = template.sudo().with_context(**(extra_ctx or {})).send_mail(
                        rec.id,
                        email_values={
                            "email_to": email,
                            "email_from": (
                                rec.company_id.email_formatted
                                or self.env.company.email_formatted
                                or self.env.user.email_formatted
                            ),
                        },
                        force_send=True,
                    )

                    mail = self.env["mail.mail"].sudo().browse(mail_id).exists()
                    _logger.warning(
                        "[LOCKER MAIL] Mail sent | Mail ID: %s | Allocation: %s | State: %s | Mail state: %s %s",
                        mail_id,
                        rec.name,
                        rec.state,
                        mail.state if mail else "sent-and-deleted",
                        (mail.failure_reason or "") if mail else "",
                    )

            except Exception:
                _logger.exception(
                    "[LOCKER MAIL] SEND FAILED | Allocation: %s | Template: %s",
                    rec.name,
                    template_xmlid,
                )
    @api.model
    def _cron_release_reserved_lockers(self):
        """Release lockers whose reservation time is over and fix stale reserved lockers."""
        now = fields.Datetime.now()
        expired = self.search([
            ("state", "=", "draft"),
            ("reserved_until", "!=", False),
            ("reserved_until", "<=", now),
        ])
        for rec in expired:
            rec.action_cancel()
            rec.message_post(body=_("Locker reservation expired. The allocation was cancelled and the locker was released."))

        stale = self.env["locker.locker"].search([("status", "=", "reserved")]).filtered(
            lambda locker: not locker.allocation_ids.filtered(lambda a: a.state == "draft")
        )
        if stale:
            stale.write({"status": "available"})

    # RENEWAL
    def _get_renewal_period(self, reference_date=None):
        self.ensure_one()
        start_date = reference_date or fields.Date.context_today(self)
        if self.state == "renewal_pending" and self.end_date and self.end_date > start_date:
            start_date = self.end_date
        return start_date, start_date + relativedelta(months=1)

    def _complete_renewal_from_invoice(self, invoice):
        """Finish the renewal once its invoice is paid: state -> Allocated, mail the person."""
        self.ensure_one()
     
        if (not invoice or invoice != self.renewal_invoice_id
                or invoice.move_type != "out_invoice" or invoice.payment_state != "paid"
                or self.state not in ("renewal_pending", "expired")):
            return False
        old_state = self.state
        start_date, end_date = self._get_renewal_period(invoice.invoice_date)
        self.write({
            "invoice_id": invoice.id,
            "renewal_invoice_id": False,
            "start_date": start_date,
            "end_date": end_date,
            "state": "allocated",
            "renewal_available": False,
            # Reset current penalty status for the new allocation period.
            "penalty_available": False,
            "penalty_start_date": False,
            "penalty_invoice_id": False,
        })
        self._sync_access_credentials()
        self._post_history(_("Locker Renewed"), [
            ("Locker", self.locker_id.display_name),
            ("Partner", self.partner_id.display_name),
            ("Previous State", dict(self._fields["state"].selection).get(old_state, old_state)),
            ("New Start Date", start_date),
            ("New End Date", end_date),
            ("Renewed By", self.env.user.name),
            ("Renewal Invoice", invoice.name),
        ])
        self._send_state_notification("iPredict_locker_management.mail_template_locker_renewed")
        return True

    def _complete_paid_renewals(self):
        """Fallback (cron): complete every renewal whose invoice has been paid."""
        allocations = self.search([
            ("state", "in", ("renewal_pending", "expired")),
            ("renewal_invoice_id", "!=", False),
        ])
        for allocation in allocations:
            invoice = allocation.renewal_invoice_id
            if invoice.payment_state == "paid":
                allocation._complete_renewal_from_invoice(invoice)

    # RENEW
    def action_renew(self):
        self.ensure_one()
        if self.state not in ("renewal_pending", "expired"):
            raise ValidationError(_("Locker renewal is not available."))

        if self.penalty_invoice_id and self.penalty_invoice_id.payment_state != "paid":
            raise ValidationError(
                _("Locker cannot be renewed until the penalty invoice is fully paid.")
            )

        if not self.renewal_available:
            raise ValidationError(_("Locker renewal is not available yet."))

        # Free Locker Renewal
        if self.allocation_type != "paid":
            old_state = self.state
            start_date, end_date = self._get_renewal_period()
            self.write({
                "start_date": start_date,
                "end_date": end_date,
                "state": "allocated",
                "renewal_available": False,
                "penalty_available": False,
                "penalty_start_date": False,
                "penalty_invoice_id": False,
            })
            self._sync_access_credentials()
            self._post_history(_("Locker Renewed"), [
                ("Locker", self.locker_id.display_name),
                ("Partner", self.partner_id.display_name),
                ("Previous State", dict(self._fields["state"].selection).get(old_state, old_state)),
                ("New Start Date", start_date),
                ("New End Date", end_date),
                ("Renewed By", self.env.user.name),
                ("Allocation Type", "Free"),
            ])
            self._send_state_notification("iPredict_locker_management.mail_template_locker_renewed")
            return {"type": "ir.actions.client", "tag": "reload"}

        # Paid Locker Renewal
        product = self.profile_id.rental_product_id
        if not product:
            raise ValidationError(_("Please configure Rental Product in Locker Profile."))

        renewal_origin = f"{self.name} - Renewal"
        renewal_invoice = self.renewal_invoice_id
        if renewal_invoice and renewal_invoice.state == "cancel":
            renewal_invoice = self.env["account.move"]

        if not renewal_invoice:
            # Invoice of the same renewal created before the link existed (never an old paid one).
            renewal_invoice = self.env["account.move"].search([
                ("invoice_origin", "=", renewal_origin),
                ("move_type", "=", "out_invoice"),
                ("partner_id", "=", self.partner_id.id),
                ("company_id", "=", self.company_id.id),
                ("state", "!=", "cancel"),
                ("payment_state", "!=", "paid"),
            ], order="id desc", limit=1)

        if renewal_invoice:
            if self.renewal_invoice_id != renewal_invoice:
                self.renewal_invoice_id = renewal_invoice.id
            if renewal_invoice.payment_state == "paid":
                if self._complete_renewal_from_invoice(renewal_invoice):
                    return {"type": "ir.actions.client", "tag": "reload"}
            return {
                "type": "ir.actions.act_window",
                "res_model": "account.move",
                "res_id": renewal_invoice.id,
                "view_mode": "form",
                "target": "current",
            }

        renewal_invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": renewal_origin,
            "invoice_date": fields.Date.context_today(self),
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                "name": f"{product.display_name} - Renewal",
                "quantity": 1,
                "price_unit": product.lst_price,
            })],
        })
        self.renewal_invoice_id = renewal_invoice.id

        self._post_history(_("Locker Renewal Invoice Created"), [
            ("Locker", self.locker_id.display_name),
            ("Partner", self.partner_id.display_name),
            ("Renewal Invoice", renewal_invoice.name),
            ("Created By", self.env.user.name),
        ])

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": renewal_invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    # CANCEL
    def action_cancel(self):
        for rec in self:
            rec.renewal_available = False
            rec.penalty_available = False
            rec.state = "cancelled"
            rec.reserved_until = False
            rec.credential_ids.write({"active": False})
            if rec.locker_id.status in ("allocated", "reserved"):
                rec.locker_id.sudo().status = "available"
            rec._post_history(_("Locker Allocation Cancelled"), [
                ("Locker", rec.locker_id.display_name),
                ("Partner", rec.partner_id.display_name),
                ("Cancelled By", self.env.user.name),
                ("Cancelled On", fields.Date.context_today(rec)),
            ])


# ACCOUNT MOVE
class AccountMove(models.Model):
    _inherit = "account.move"

    def _complete_paid_locker_renewals(self):
        paid_invoices = self.filtered(
            lambda invoice: invoice.move_type == "out_invoice" and invoice.payment_state == "paid"
        )
        if not paid_invoices:
            return
        # First payment of a draft allocation -> Allocated directly.
        self.env["locker.allocation"].sudo().search([
            ("invoice_id", "in", paid_invoices.ids),
            ("state", "=", "draft"),
        ])._allocate_from_paid_invoice()
        # Only the open renewal invoice of an allocation renews it (matched by link, not by name).
        allocations = self.env["locker.allocation"].sudo().search([
            ("renewal_invoice_id", "in", paid_invoices.ids),
            ("state", "in", ("renewal_pending", "expired")),
        ])
        for allocation in allocations:
            allocation._complete_renewal_from_invoice(allocation.renewal_invoice_id)

    def write(self, vals):
        result = super().write(vals)
        if "payment_state" in vals or "state" in vals:
            self._complete_paid_locker_renewals()
        return result


# ACCOUNT PAYMENT
class AccountPayment(models.Model):
    _inherit = "account.payment"

    def action_post(self):
        result = super().action_post()
        for payment in self:
            payment.reconciled_invoice_ids._complete_paid_locker_renewals()
        return result


# ACCOUNT PARTIAL RECONCILE
class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    @api.model_create_multi
    def create(self, vals_list):
        """The invoice payment state changes through the reconciliation (not through a write on
        the invoice), so this is where a paid renewal invoice is noticed immediately."""
        records = super().create(vals_list)
        moves = records.debit_move_id.move_id | records.credit_move_id.move_id
        moves._complete_paid_locker_renewals()
        return records