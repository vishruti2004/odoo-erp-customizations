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
    )
    locker_location_id = fields.Many2one(
    "locker.location",
    string="Locker Location",
    required=True,
    tracking=True,
    domain="[('company_id', '=', company_id)]",
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
        Sequence = self.env["ir.sequence"]

        for vals in vals_list:
            company_id = vals.get("company_id") or self.env.company.id

            if vals.get("name", _("New")) == _("New"):
                company = self.env["res.company"].browse(company_id)

                sequence_code = f"locker.locker.{company_id}"

                sequence = Sequence.search(
                    [
                        ("code", "=", sequence_code),
                        ("company_id", "=", company_id),
                    ],
                    limit=1,
                )

                if not sequence:
                    sequence = Sequence.create({
                        "name": f"Locker - {company.name}",
                        "code": sequence_code,
                        "company_id": company_id,
                        "prefix": "LK/%(year)s/",
                        "padding": 5,
                        "number_increment": 1,
                        "use_date_range": True,
                    })

                vals["name"] = sequence.next_by_id()

        return super().create(vals_list)

    def action_open_3d_view(self):
        return {
            "type": "ir.actions.client",
            "tag": "locker_3d_view",
            "name": _("3D Locker View"),
            "context": {"default_company_id": self.company_id.id},
        }

    @api.model
    def update_locker_position(self, locker_id, pos_x, pos_y, pos_z):
        locker = self.browse(locker_id)
        if locker.exists():
            locker.write({
                'pos_x': float(pos_x),
                'pos_y': float(pos_y),
                'pos_z': float(pos_z),
            })
            return True
        return False

    @api.model
    def get_3d_data(self, company_id=None):
        domain = [("active", "=", True)]

        if company_id:
            domain.append(("company_id", "=", company_id))

        lockers = self.search(
            domain,
            order="locker_location_id, profile_id, name, id"
        )

        location_data = {}

        for locker in lockers:
            location = locker.locker_location_id
            location_id = location.id or 0
            location_name = location.name or "Unassigned"

            if location_id not in location_data:
                location_data[location_id] = {
                    "location_id": location_id,
                    "locker_location_id": location_id,
                    "location": location_name,
                    "lockers": [],
                }

            location_data[location_id]["lockers"].append({
                "id": locker.id,
                "name": locker.name,
                "status": locker.status,
                "company_id": locker.company_id.id,
                "locker_location_id": locker.locker_location_id.id,
                "locker_location": locker.locker_location_id.name or "",
                "profile_id": locker.profile_id.id,
                "profile_color": locker.profile_id.color,
                "profile": locker.profile_id.name,

                "pos_x": float(locker.pos_x or 0.0),
                "pos_y": float(locker.pos_y or 0.0),
                "pos_z": float(locker.pos_z or 0.0),

                # Dimensions
                "w": float(locker.width or 1.0),
                "h": float(locker.height or 2.0),
                "d": float(locker.depth or 1.0),
            })

        result = list(location_data.values())
        result.sort(key=lambda loc: loc["location"].lower())

        return result

    @api.model
    def get_locker_locations(self, company_id):
        locations = self.env["locker.location"].search(
            [("company_id", "=", company_id)],
            order="name",
        )

        return [
            {
                "id": loc.id,
                "name": loc.name,
            }
            for loc in locations
        ]

    @api.model
    def get_locker_details(self, locker_id):
        locker = self.browse(locker_id)

        allocation = self.env["locker.allocation"].search(
            [
                ("locker_id", "=", locker.id),
                ("state", "=", "allocated"),
            ],
            limit=1,
        )

        return {
            "name": locker.name,
            "profile": locker.profile_id.name or "",
            "locker_location": locker.locker_location_id.name or "",
            "status": locker.status,
            "partner": allocation.partner_id.name if allocation else "",
            "start_date": str(allocation.start_date) if allocation else "",
            "end_date": str(allocation.end_date) if allocation else "",
        }