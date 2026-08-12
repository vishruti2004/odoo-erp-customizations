# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LockerAccess(models.Model):
    _name = "locker.access"
    _description = "Locker Check In / Check Out"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Allocation Partner",
        required=True,
        tracking=True,
        ondelete="restrict",
    )

    authenticated_partner_id = fields.Many2one(
        "res.partner",
        string="Authenticated Person",
        required=True,
        tracking=True,
        ondelete="restrict",
    )

    allocation_id = fields.Many2one(
        "locker.allocation",
        string="Locker Allocation",
        required=True,
        tracking=True,
        ondelete="restrict",
    )

    locker_id = fields.Many2one(
        "locker.locker",
        string="Locker",
        related="allocation_id.locker_id",
        store=True,
        readonly=True,
    )

    profile_id = fields.Many2one(
        "locker.profile",
        string="Locker Profile",
        related="allocation_id.profile_id",
        store=True,
        readonly=True,
    )

    access_method = fields.Selection(
        related="allocation_id.access_method",
        string="Access Method",
        store=True,
        readonly=True,
    )

    check_in_time = fields.Datetime(
        string="Check In",
        readonly=True,
        tracking=True,
    )

    check_out_time = fields.Datetime(
        string="Check Out",
        readonly=True,
        tracking=True,
    )

    companion_count = fields.Integer(
        string="Additional People",
        default=0,
        required=True,
        tracking=True,
        help="Number of additional people entering with the authenticated person.",
    )

    total_people = fields.Integer(
        string="Total People",
        compute="_compute_total_people",
        store=True,
    )

    state = fields.Selection(
        [
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
        ],
        string="Status",
        default="checked_out",
        required=True,
        tracking=True,
    )

    @api.depends("companion_count")
    def _compute_total_people(self):
        for rec in self:
            rec.total_people = 1 + max(rec.companion_count or 0, 0)

    @api.constrains("companion_count")
    def _check_companion_count(self):
        for rec in self:
            if rec.companion_count < 0:
                raise ValidationError(
                    _("Additional people count cannot be negative.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("locker.access")
                    or "New"
                )

            if (
                not vals.get("authenticated_partner_id")
                and vals.get("partner_id")
            ):
                vals["authenticated_partner_id"] = vals["partner_id"]

            if vals.get("companion_count") is None:
                vals["companion_count"] = 0

        records = super().create(vals_list)
        records._check_authenticated_person()
        return records

    def _check_authenticated_person(self):
        for rec in self:
            if not rec.allocation_id:
                continue

            if not rec.authenticated_partner_id:
                raise ValidationError(
                    _("Authenticated Person is required.")
                )

            allowed_partner_ids = (
                rec.allocation_id.authorized_partner_ids.ids
                + [rec.allocation_id.partner_id.id]
            )

            if rec.authenticated_partner_id.id not in allowed_partner_ids:
                raise ValidationError(
                    _(
                        "The authenticated person '%s' is not authorized "
                        "for this locker."
                    )
                    % rec.authenticated_partner_id.display_name
                )

    def action_check_in(self):
        for rec in self:
            if rec.state == "checked_in":
                raise ValidationError(
                    _("This person is already checked in.")
                )

            rec._check_authenticated_person()

            rec.write(
                {
                    "check_in_time": fields.Datetime.now(),
                    "state": "checked_in",
                }
            )

    def action_check_out(self):
        for rec in self:
            if rec.state != "checked_in":
                raise ValidationError(
                    _("This person is not currently checked in.")
                )

            rec.write(
                {
                    "check_out_time": fields.Datetime.now(),
                    "state": "checked_out",
                }
            )