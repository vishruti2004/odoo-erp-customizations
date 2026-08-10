# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LockerAccess(models.Model):
    _name = "locker.access"
    _description = "Locker Check In / Check Out"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default="New", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Allocation Partner", required=True, tracking=True, ondelete="restrict")
    authenticated_partner_id = fields.Many2one("res.partner", string="Authenticated Person", required=True, tracking=True, ondelete="restrict")
    allocation_id = fields.Many2one("locker.allocation", string="Locker Allocation", required=True, tracking=True, ondelete="restrict")
    locker_id = fields.Many2one("locker.locker", string="Locker", related="allocation_id.locker_id", store=True, readonly=True)
    profile_id = fields.Many2one("locker.profile", string="Locker Profile", related="allocation_id.profile_id", store=True, readonly=True)
    access_method = fields.Selection(related="allocation_id.access_method", string="Access Method", store=True, readonly=True)
    check_in_time = fields.Datetime(string="Check In", readonly=True, tracking=True)
    check_out_time = fields.Datetime(string="Check Out", readonly=True, tracking=True)
    state = fields.Selection([("checked_in", "Checked In"), ("checked_out", "Checked Out")], string="Status", default="checked_out", required=True, tracking=True)

    # Create record validation & sequence generation
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("locker.access") or "New"
            if not vals.get("authenticated_partner_id") and vals.get("partner_id"):
                vals["authenticated_partner_id"] = vals["partner_id"]
        records = super().create(vals_list)
        records._check_authenticated_person()
        return records

    # Validate authenticated person authorization
    def _check_authenticated_person(self):
        for rec in self:
            if not rec.allocation_id:
                continue
            if not rec.authenticated_partner_id:
                raise ValidationError(_("Authenticated Person is required."))
            allowed_partner_ids = rec.allocation_id.authorized_partner_ids.ids + [rec.allocation_id.partner_id.id]
            if rec.authenticated_partner_id.id not in allowed_partner_ids:
                raise ValidationError(_("The authenticated person '%s' is not authorized for this locker.") % rec.authenticated_partner_id.display_name)

    # Perform check in action
    def action_check_in(self):
        for rec in self:
            if rec.state == "checked_in":
                raise ValidationError(_("This person is already checked in."))
            rec._check_authenticated_person()
            rec.write({"check_in_time": fields.Datetime.now(), "state": "checked_in"})

    # Perform check out action
    def action_check_out(self):
        for rec in self:
            if rec.state != "checked_in":
                raise ValidationError(_("This person is not currently checked in."))
            rec.write({"check_out_time": fields.Datetime.now(), "state": "checked_out"})