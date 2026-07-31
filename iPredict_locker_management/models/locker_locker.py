# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class LockerLocker(models.Model):
    _name = "locker.locker"
    _description = "Locker"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    name = fields.Char(string="Locker", required=True, copy=False, default=lambda self: _("New"), tracking=True)
    profile_id = fields.Many2one("locker.profile", string="Locker Profile", required=True, ondelete="restrict", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, tracking=True)
    status = fields.Selection([("available", "Available"), ("allocated", "Allocated")], string="Status", default="available", required=True, tracking=True, copy=False)
    active = fields.Boolean(default=True, tracking=True)
    note = fields.Html(string="Notes")
    allocation_ids = fields.One2many("locker.allocation", "locker_id", string="Allocations")
    allocation_count = fields.Integer(string="Allocation Count", compute="_compute_allocation_count")
    current_allocation_id = fields.Many2one("locker.allocation", string="Current Allocation", compute="_compute_current_allocation")

    @api.depends("allocation_ids")
    def _compute_allocation_count(self):
        for rec in self:
            rec.allocation_count = len(rec.allocation_ids)

    @api.depends("allocation_ids.state")
    def _compute_current_allocation(self):
        for rec in self:
            allocation = self.env["locker.allocation"].search(
                [
                    ("locker_id", "=", rec.id),
                    ("state", "=", "allocated"),
                ],
                order="id desc",
                limit=1,
            )
            rec.current_allocation_id = allocation


    def action_view_allocations(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Locker Allocations",
            "res_model": "locker.allocation",
            "view_mode": "list,form",
            "domain": [("locker_id", "=", self.id)],
            "context": {
                "default_locker_id": self.id,
            },
        }

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "locker.locker"
                ) or _("New")

        return super().create(vals_list)