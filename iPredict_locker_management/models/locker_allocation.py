# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LockerAllocation(models.Model):
    _name = "locker.allocation"
    _description = "Locker Allocation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "id desc"

    # Allocation identity & relation fields
    name = fields.Char(
        string="Allocation Number",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
    )
    locker_id = fields.Many2one(
        "locker.locker",
        string="Locker",
        required=True,
        ondelete="restrict",
        tracking=True,
        domain="[('status', '=', 'available'), ('company_id', '=', company_id)]",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        tracking=True,
        ondelete="restrict",
    )
    start_date = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    end_date = fields.Date(
        string="End Date",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("allocated", "Allocated"),
            ("returned", "Returned"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
        copy=False,
    )
    note = fields.Html()

    # Related locker profile attributes
    profile_id = fields.Many2one(
        "locker.profile",
        related="locker_id.profile_id",
        readonly=True,
    )
    access_method = fields.Selection(
        related="profile_id.access_method",
        string="Access Method",
        store=True,
        readonly=True,
    )
    allocation_type = fields.Selection(
        related="locker_id.profile_id.allocation_type",
        string="Allocation Type",
        store=True,
        readonly=True,
    )

    # Invoicing & payment relations
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        readonly=True,
        copy=False,
        tracking=True,
    )
    payment_state = fields.Selection(
        related="invoice_id.payment_state",
        string="Payment Status",
        readonly=True,
    )
    invoice_count = fields.Integer(
        compute="_compute_invoice_count",
    )

    # Access authorization & authentication credentials
    authorized_partner_ids = fields.Many2many(
        "res.partner",
        string="Authorized Persons",
        tracking=True,
    )
    credential_ids = fields.One2many(
        "locker.access.credential",
        "allocation_id",
        string="Authentication Credentials",
        copy=False,
    )

    # Legacy authentication fields kept for compatibility
    pin_code = fields.Char(
        string="Locker PIN",
        copy=False,
        readonly=True,
        tracking=True,
    )
    qr_token = fields.Char(
        string="QR Token",
        copy=False,
        readonly=True,
        tracking=True,
    )
    rfid_uid = fields.Char(
        string="RFID UID",
        copy=False,
        tracking=True,
    )
    biometric_id = fields.Char(
        string="Biometric ID",
        copy=False,
        tracking=True,
    )

    # ---------------------------------------------------------
    # INVOICE COUNT
    # ---------------------------------------------------------

    @api.depends("invoice_id")
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = 1 if rec.invoice_id else 0

    # ---------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(
            self._prepare_create_vals(vals_list)
        )

        for record in records:
            record._sync_access_credentials()

        return records

    def _prepare_create_vals(self, vals_list):
        for vals in vals_list:
            company_id = (
                vals.get("company_id")
                or self.env.company.id
            )

            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company_id)
                    .next_by_code("locker.allocation")
                    or "New"
                )

        return vals_list

    # ---------------------------------------------------------
    # WRITE
    # ---------------------------------------------------------

    def write(self, vals):
        credential_model = self.env[
            "locker.access.credential"
        ].sudo()

        # If the locker changes, the access method may also change.
        # Old digital credentials must never remain attached to the
        # new method.
        if "locker_id" in vals:
            for allocation in self:
                old_credentials = credential_model.search(
                    [
                        ("allocation_id", "=", allocation.id),
                        ("active", "=", True),
                    ]
                )
                if old_credentials:
                    old_credentials.action_clear_credential()

        result = super().write(vals)

        if (
            "partner_id" in vals
            or "authorized_partner_ids" in vals
            or "locker_id" in vals
        ):
            self._sync_access_credentials()

        return result

    # ---------------------------------------------------------
    # SYNC AUTHORIZED PERSON CREDENTIALS
    # ---------------------------------------------------------

    def _sync_access_credentials(self):
        Credential = self.env[
            "locker.access.credential"
        ].sudo()

        for allocation in self:
            if not allocation.id:
                continue

            partner_ids = set()

            if allocation.partner_id:
                partner_ids.add(
                    allocation.partner_id.id
                )

            partner_ids.update(
                allocation.authorized_partner_ids.ids
            )

            # Create missing credentials and automatically generate
            # the credential for PIN / RFID / QR.
            for partner_id in partner_ids:
                credential = Credential.search(
                    [
                        (
                            "allocation_id",
                            "=",
                            allocation.id,
                        ),
                        (
                            "partner_id",
                            "=",
                            partner_id,
                        ),
                    ],
                    limit=1,
                )

                if not credential:
                    credential = Credential.create({
                        "allocation_id": allocation.id,
                        "partner_id": partner_id,
                        "active": True,
                    })
                else:
                    credential.active = True

                access_method = allocation.access_method

                if access_method in (
                    "pin",
                    "rfid",
                    "qr",
                ):
                    # Generate only if the credential for the
                    # current method is missing.
                    has_value = (
                        bool(credential.pin_code)
                        if access_method == "pin"
                        else bool(credential.rfid_uid)
                        if access_method == "rfid"
                        else bool(
                            credential.qr_token
                            and credential.qr_code
                        )
                    )

                    if not has_value:
                        credential.action_generate_credential()

                elif access_method == "physical_key":
                    # Physical key needs no digital credential.
                    if (
                        credential.pin_code
                        or credential.rfid_uid
                        or credential.qr_token
                        or credential.qr_code
                        or credential.biometric_id
                    ):
                        credential.action_clear_credential()

                elif access_method == "biometric":
                    # Biometric ID is registered by the biometric
                    # device; do not generate a fake ID.
                    if (
                        credential.pin_code
                        or credential.rfid_uid
                        or credential.qr_token
                        or credential.qr_code
                    ):
                        credential.action_clear_credential()

            # Deactivate credentials of removed persons.
            credentials = Credential.search([
                (
                    "allocation_id",
                    "=",
                    allocation.id,
                ),
            ])

            for credential in credentials:
                if credential.partner_id.id not in partner_ids:
                    credential.active = False
                else:
                    credential.active = True

    # ---------------------------------------------------------
    # CREATE INVOICE
    # ---------------------------------------------------------

    def action_create_invoice(self):
        self.ensure_one()

        if self.allocation_type != "paid":
            raise ValidationError(
                _("Invoice is not required for Free Locker.")
            )

        if self.invoice_id:
            raise ValidationError(
                _("Invoice already exists.")
            )

        product = self.profile_id.rental_product_id

        if not product:
            raise ValidationError(
                _(
                    "Please configure Rental Product "
                    "in Locker Profile."
                )
            )

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": self.name,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": product.display_name,
                        "quantity": 1,
                        "price_unit": product.lst_price,
                    },
                )
            ],
        })

        self.invoice_id = invoice.id

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": invoice.id,
            "view_mode": "form",
            "target": "current",
        }

    # ---------------------------------------------------------
    # VIEW INVOICE
    # ---------------------------------------------------------

    def action_view_invoice(self):
        self.ensure_one()

        if not self.invoice_id:
            raise ValidationError(
                _("No invoice found.")
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    # ---------------------------------------------------------
    # ALLOCATE
    # ---------------------------------------------------------

    def action_allocate(self):
        for rec in self:
            if not rec.locker_id:
                raise ValidationError(
                    _("Please select a locker.")
                )

            if not rec.partner_id:
                raise ValidationError(
                    _("Please select a partner.")
                )

            if not rec.profile_id:
                raise ValidationError(
                    _(
                        "The selected locker does not have "
                        "a Locker Profile."
                    )
                )

            if rec.allocation_type == "paid":
                if not rec.invoice_id:
                    raise ValidationError(
                        _("Please create the invoice first.")
                    )

                if rec.invoice_id.state != "posted":
                    raise ValidationError(
                        _("Please post the invoice first.")
                    )

                if rec.invoice_id.payment_state != "paid":
                    raise ValidationError(
                        _(
                            "Please register the payment before "
                            "allocating the locker."
                        )
                    )

            existing = self.search(
                [
                    ("id", "!=", rec.id),
                    ("locker_id", "=", rec.locker_id.id),
                    ("state", "=", "allocated"),
                ],
                limit=1,
            )

            if existing:
                raise ValidationError(
                    _(
                        "Locker '%s' is already allocated to '%s'."
                    )
                    % (
                        rec.locker_id.display_name,
                        existing.partner_id.display_name,
                    )
                )

            # Ensure every authorized person has the correct
            # credential before allocation.
            rec._sync_access_credentials()

            rec.state = "allocated"
            rec.locker_id.status = "allocated"

    # ---------------------------------------------------------
    # RETURN
    # ---------------------------------------------------------

    def action_return(self):
        for rec in self:
            rec.state = "returned"
            rec.locker_id.status = "available"
            rec.credential_ids.write({
                "active": False,
            })

    # ---------------------------------------------------------
    # CANCEL
    # ---------------------------------------------------------

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            rec.credential_ids.write({
                "active": False,
            })

            if rec.locker_id.status == "allocated":
                rec.locker_id.status = "available"