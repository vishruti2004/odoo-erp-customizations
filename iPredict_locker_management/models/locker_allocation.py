# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LockerAllocation(models.Model):
    _name = "locker.allocation"
    _description = "Locker Allocation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "id desc"

    name = fields.Char(string="Allocation Number", required=True, copy=False, readonly=True, default="New", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, tracking=True)
    locker_id = fields.Many2one("locker.locker", string="Locker", required=True, ondelete="restrict", tracking=True, domain="[('status', '=', 'available'), ('company_id', '=', company_id)]")
    partner_id = fields.Many2one("res.partner", string="Partner", required=True, tracking=True)
    start_date = fields.Date(string="Start Date", required=True, default=fields.Date.context_today, tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    state = fields.Selection([("draft", "Draft"), ("allocated", "Allocated"), ("returned", "Returned"), ("cancelled", "Cancelled")], default="draft", tracking=True, copy=False)
    note = fields.Html()
    profile_id = fields.Many2one("locker.profile", related="locker_id.profile_id", readonly=True)
    allocation_type = fields.Selection(related="locker_id.profile_id.allocation_type", string="Allocation Type", store=True, readonly=True)
    invoice_id = fields.Many2one("account.move", string="Invoice", readonly=True, copy=False, tracking=True)
    payment_state = fields.Selection(related="invoice_id.payment_state", string="Payment Status", readonly=True)
    invoice_count = fields.Integer(compute="_compute_invoice_count")


    @api.depends("invoice_id")
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = 1 if rec.invoice_id else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id

            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company_id)
                    .next_by_code("locker.allocation")
                    or "New"
                )

        return super().create(vals_list)

    # Actions

    def action_create_invoice(self):
        self.ensure_one()

        if self.allocation_type != "paid":
            raise ValidationError(_("Invoice is not required for Free Locker."))

        if self.invoice_id:
            raise ValidationError(_("Invoice already exists."))

        product = self.profile_id.rental_product_id

        if not product:
            raise ValidationError(
                _("Please configure Rental Product in Locker Profile.")
            )

        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "invoice_origin": self.name,
            "invoice_line_ids": [
                (0, 0, {
                    "product_id": product.id,
                    "name": product.display_name,
                    "quantity": 1,
                    "price_unit": product.lst_price,
                })
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

    def action_view_invoice(self):
        self.ensure_one()

        if not self.invoice_id:
            raise ValidationError(_("No invoice found."))

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.invoice_id.id,
        }

    def action_allocate(self):
        for rec in self:
            # Paid Locker Validation
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
                            "Please register the payment before allocating the"
                            " locker."
                        )
                    )

            existing = self.search([
                ("id", "!=", rec.id),
                ("locker_id", "=", rec.locker_id.id),
                ("state", "=", "allocated"),
            ], limit=1)

            if existing:
                raise ValidationError(
                    _("Locker '%s' is already allocated to '%s'.")
                    % (
                        rec.locker_id.display_name,
                        existing.partner_id.display_name,
                    )
                )

            rec.state = "allocated"
            rec.locker_id.status = "allocated"

    def action_return(self):
        for rec in self:
            rec.state = "returned"
            rec.locker_id.status = "available"

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"

            if rec.locker_id.status == "allocated":
                rec.locker_id.status = "available"