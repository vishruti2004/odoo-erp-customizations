# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError

class LockerAllocation(models.Model):
    _name = "locker.allocation"
    _description = "Locker Allocation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "id desc"

    name = fields.Char(string="Allocation Number", required=True, copy=False, readonly=True, default="New", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, tracking=True)
    locker_id = fields.Many2one("locker.locker", string="Locker", required=True, ondelete="restrict", tracking=True, domain="[('status','=','available')]")
    partner_id = fields.Many2one("res.partner", string="Partner", required=True, tracking=True)
    start_date = fields.Date(string="Start Date", required=True, default=fields.Date.context_today, tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    state = fields.Selection([("draft", "Draft"), ("allocated", "Allocated"), ("returned", "Returned"), ("cancelled", "Cancelled")], string="Status", default="draft", required=True, tracking=True, copy=False)
    note = fields.Html(string="Notes")

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = sequence.next_by_code("locker.allocation") or "New"
        return super().create(vals_list)

    @api.constrains("locker_id", "state")
    def _check_active_allocation(self):
        for rec in self:
            if rec.state == "allocated":
                allocation = self.search([
                    ("id", "!=", rec.id),
                    ("locker_id", "=", rec.locker_id.id),
                    ("state", "=", "allocated"),
                ], limit=1)
                if allocation:
                    raise ValidationError("This locker is already allocated.")
    # Actions

    def action_allocate(self):
        for rec in self:
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