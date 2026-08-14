# -*- coding: utf-8 -*-

from odoo import _, api, fields, models, Command
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


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
    authorized_partner_ids = fields.Many2many("res.partner", string="Authorized Persons", tracking=True)
    credential_ids = fields.One2many("locker.access.credential", "allocation_id", string="Authentication Credentials", copy=False)
    pin_code = fields.Char(string="Locker PIN", copy=False, readonly=True, tracking=True)
    qr_token = fields.Char(string="QR Token", copy=False, readonly=True, tracking=True)
    rfid_uid = fields.Char(string="RFID UID", copy=False, tracking=True)
    biometric_id = fields.Char(string="Biometric ID", copy=False, tracking=True)
    return_reason_id = fields.Many2one("locker.return.reason", string="Return Reason", readonly=True, copy=False, tracking=True)
    return_date = fields.Date(string="Return Date", readonly=True, copy=False)

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
    # CHATTER HISTORY
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
            record._sync_access_credentials()
        return records

    def _prepare_create_vals(self, vals_list):
        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].with_company(company_id).next_by_code("locker.allocation") or "New"
        return vals_list

    def write(self, vals):
        for allocation in self:
            if allocation.state not in ("renewal_pending", "expired"):
                vals["renewal_available"] = False
                break
        result = super().write(vals)
        if any(field in vals for field in ("partner_id", "authorized_partner_ids", "locker_id")):
            self._sync_access_credentials()
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

    # INVOICING
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

        product = self.profile_id.rental_product_id
        if not product:
            raise ValidationError(
                _("Please configure Rental Product in Locker Profile.")
            )

        period_labels = {
            "day": _("Day"),
            "month": _("Month"),
            "year": _("Year"),
        }
        period_label = period_labels.get(penalty.period, _("Penalty"))

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": f"{self.name} - Penalty",
            "invoice_date": today,
            "invoice_line_ids": [Command.create({
                "product_id": product.id,
                # "name": f"{product.display_name} - Penalty ({period_label})",
                "name": (
                    f"{product.display_name} - Penalty ({period_label})\n"
                    f"{self.penalty_start_date.strftime('%d/%m/%Y')} to "
                    f"{today.strftime('%d/%m/%Y')} - {penalty_days} Days"
                ),
                "quantity": 1,
                "price_unit": penalty_amount,
            })],
        })

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

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

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
            rec.locker_id.status = "allocated"
            rec._post_history(_("Locker Allocated"), [
                ("Locker", rec.locker_id.display_name),
                ("Allocated To", rec.partner_id.display_name),
                ("Start Date", rec.start_date),
                ("End Date", rec.end_date),
                ("Allocated By", self.env.user.name),
            ])

    # RETURN
    def action_return(self):
        self.ensure_one()
        if self.state not in ("allocated", "renewal_pending", "expired"):
            raise ValidationError(_("Locker return is not allowed in current state."))

        # If penalty invoice exists and is not paid, return is not allowed.
        if self.penalty_invoice_id and self.penalty_invoice_id.payment_state != "paid":
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

    # RENEWAL AUTOMATION + PENALTY CRON
    @api.model
    def _cron_update_renewal_availability(self):
        today = fields.Date.context_today(self)
        allocations = self.search([("state", "in", ("allocated", "renewal_pending", "expired")), ("end_date", "!=", False)])
        for rec in allocations:
            company = rec.company_id
            # RENEWAL LOGIC
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
            if old_state != new_state:
                rec.state = new_state
                rec.renewal_available = renewal_available
                if new_state == "renewal_pending":
                    rec._post_history(_("Locker Renewal Pending"), [
                        ("Locker", rec.locker_id.display_name),
                        ("Partner", rec.partner_id.display_name),
                        ("End Date", rec.end_date),
                        ("Renewal Reminder Date", renewal_date),
                    ])
                elif new_state == "expired":
                    rec._post_history(_("Locker Expired"), [
                        ("Locker", rec.locker_id.display_name),
                        ("Partner", rec.partner_id.display_name),
                        ("End Date", rec.end_date),
                        ("Expired On", today),
                    ])
            # PENALTY LOGIC
            # PENALTY LOGIC
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

            # If penalty invoice already exists, do not create another penalty.
            if rec.penalty_invoice_id:
                rec.penalty_available = False
                continue

            penalty_start_date = rec.end_date + relativedelta(
                days=penalty.start_after_days or 0
            )
            rec.penalty_start_date = penalty_start_date
            rec.penalty_available = today >= penalty_start_date
        # Existing renewal completion
        self._complete_paid_renewals()
        # Clear renewal availability where not applicable
        self.search([("state", "in", ("draft", "returned", "cancelled")), ("renewal_available", "=", True)]).write({"renewal_available": False})

    # RENEWAL FROM PAID INVOICE
    def _complete_renewal_from_invoice(self, invoice):
        self.ensure_one()
        if (not invoice or invoice.move_type != "out_invoice" or invoice.payment_state != "paid"
                or invoice.invoice_origin != f"{self.name} - Renewal"
                or self.state not in ("renewal_pending", "expired", "allocated")):
            return False
        old_state = self.state
        start_date = invoice.invoice_date or fields.Date.context_today(self)
        end_date = start_date + relativedelta(months=1)
        self.write({
            "invoice_id": invoice.id,
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
        return True

    def _complete_paid_renewals(self):
        renewal_invoices = self.env["account.move"].search([("move_type", "=", "out_invoice"), ("payment_state", "=", "paid")])
        for invoice in renewal_invoices:
            if not invoice.invoice_origin or not invoice.invoice_origin.endswith(" - Renewal"):
                continue
            allocation_name = invoice.invoice_origin[:-10]
            allocation = self.search([
                ("name", "=", allocation_name),
                ("partner_id", "=", invoice.partner_id.id),
                ("company_id", "=", invoice.company_id.id),
                ("state", "in", ("renewal_pending", "expired")),
            ], limit=1)
            if allocation:
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
            today = fields.Date.context_today(self)
            self.write({
                "start_date": today,
                "end_date": today + relativedelta(months=1),
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
                ("Start Date", today),
                ("Renewed By", self.env.user.name),
                ("Allocation Type", "Free"),
            ])
            return {"type": "ir.actions.client", "tag": "reload"}

        # Paid Locker Renewal
        product = self.profile_id.rental_product_id
        if not product:
            raise ValidationError(_("Please configure Rental Product in Locker Profile."))

        renewal_origin = f"{self.name} - Renewal"
        renewal_invoice = self.env["account.move"].search([
            ("invoice_origin", "=", renewal_origin),
            ("move_type", "=", "out_invoice"),
            ("partner_id", "=", self.partner_id.id),
            ("company_id", "=", self.company_id.id),
        ], order="id desc", limit=1)

        if renewal_invoice:
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
            rec.credential_ids.write({"active": False})
            if rec.locker_id.status == "allocated":
                rec.locker_id.status = "available"
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
        renewal_invoices = self.filtered(lambda invoice: (
            invoice.move_type == "out_invoice" and invoice.payment_state == "paid"
            and invoice.invoice_origin and invoice.invoice_origin.endswith(" - Renewal")
        ))
        if not renewal_invoices:
            return
        Allocation = self.env["locker.allocation"]
        for invoice in renewal_invoices:
            allocation_name = invoice.invoice_origin[:-10]
            allocation = Allocation.search([
                ("name", "=", allocation_name),
                ("partner_id", "=", invoice.partner_id.id),
                ("company_id", "=", invoice.company_id.id),
                ("state", "in", ("renewal_pending", "expired", "allocated")),
            ], limit=1)
            if allocation:
                allocation._complete_renewal_from_invoice(invoice)

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
            invoices = payment.reconciled_invoice_ids.filtered(lambda invoice: (
                invoice.move_type == "out_invoice" and invoice.payment_state == "paid"
                and invoice.invoice_origin and invoice.invoice_origin.endswith(" - Renewal")
            ))
            invoices._complete_paid_locker_renewals()
        return result