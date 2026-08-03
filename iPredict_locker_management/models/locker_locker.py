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
    location_id = fields.Many2one(
        "stock.location",
        string="Location",
        domain="[('usage','=','internal')]",
        tracking=True,
        required=True,
    )

    # 3D VIEW FIELDS
    pos_x = fields.Float(string="Position X", default=0.0)
    pos_y = fields.Float(string="Position Y", default=0.0)
    pos_z = fields.Float(string="Position Z", default=0.0)
    width = fields.Float(string="Width", default=1.0)
    height = fields.Float(string="Height", default=1.0)
    depth = fields.Float(string="Depth", default=1.0)

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

            company_id = vals.get("company_id", self.env.company.id)

            if vals.get("name", _("New")) == _("New"):
                vals["name"] = (
                    self.env["ir.sequence"]
                    .with_company(company_id)
                    .next_by_code("locker.locker")
                    or _("New")
                )

        return super().create(vals_list)

    def action_open_3d_view(self):
        return {
            "type": "ir.actions.client",
            "tag": "locker_3d_view",
            "name": _("3D Locker View"),
            "context": {"default_company_id": self.company_id.id},
        }

    @api.model
    def get_3d_data(self, company_id=None):
        domain = [("active", "=", True)]
        if company_id:
            domain.append(("company_id", "=", company_id))

        lockers = self.search(domain)
        result = []
        for locker in lockers:
            result.append({
                "id": locker.id,
                "name": locker.name,
                "status": locker.status,
                "location": locker.location_id.complete_name or locker.location_id.name,
                "x": locker.pos_x,
                "y": locker.pos_y,
                "z": locker.pos_z,
                "w": locker.width or 1.0,
                "h": locker.height or 1.0,
                "d": locker.depth or 1.0,
            })
        return result