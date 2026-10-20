from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class LockerLocker(models.Model):
    _name = "locker.locker"
    _description = "Locker"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _order = "name"

    name = fields.Char(string="Locker", required=True, copy=False, default=lambda self: _("New"), tracking=True)
    profile_id = fields.Many2one("locker.profile", string="Locker Profile", required=True, ondelete="restrict", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company, required=True, tracking=True)
    status = fields.Selection([("available", "Available"), ("reserved", "Reserved"), ("allocated", "Allocated")], string="Status", default="available", required=True, tracking=True, copy=False)
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
    site_id = fields.Many2one(
    "locker.site",
    string="Site",
    ondelete="restrict",
    index=True,
)
    side = fields.Selection(
        [
            ("side_1", "Side 1"),
            ("side_2", "Side 2"),
        ],
        string="Side",
        default="side_1",
        required=True,
        index=True,
    )
  
    # 3D VIEW FIELDS
    pos_x = fields.Float(string="Position X", default=0.0)
    pos_y = fields.Float(string="Position Y", default=0.0)
    pos_z = fields.Float(string="Position Z", default=0.0)
    width = fields.Float(string="Width", default=1.0)
    height = fields.Float(string="Height", default=1.0)
    depth = fields.Float(string="Depth", default=1.0)

    current_allocation_id = fields.Many2one(
        "locker.allocation",
        string="Current Allocation",
        compute="_compute_current_allocation",
    )

    @api.depends("allocation_ids.state")
    def _compute_current_allocation(self):
        active_states = ("allocated", "renewal_pending", "expired")
        for rec in self:
            allocations = rec.allocation_ids.filtered(lambda a: a.state in active_states)
            rec.current_allocation_id = allocations.sorted("id", reverse=True)[:1]

    def write(self, vals):
        result = super().write(vals)
        if vals.get("status") == "available":
            self._auto_check_out_people()
        return result

    def _auto_check_out_people(self):
        """Locker became available -> everybody still checked in on it is checked out."""
        accesses = self.env["locker.access"].sudo().search([
            ("locker_id", "in", self.ids),
            ("state", "=", "checked_in"),
        ])
        for access in accesses:
            access.action_check_out()
            access.message_post(
                body=_("Automatically checked out because the locker became available.")
            )

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

    def action_view_access_history(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Access History"),
            "res_model": "locker.access",
            "view_mode": "list,form",
            "domain": [("locker_id", "=", self.id)],
        }

    def action_open_locker_allocation(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": _("Locker Allocation"),
            "res_model": "locker.allocation",
            "view_mode": "form",
            "view_id": self.env.ref(
                "iPredict_locker_management.view_locker_allocation_form"
            ).id,
            "target": "current",
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
    def get_3d_data(self, company_id=None):
        is_admin = self.env.user.has_group(
            "iPredict_locker_management.group_locker_admin"
        )

        Company = self.env["res.company"]
        Location = self.env["locker.location"]
        Site = self.env["locker.site"]
        Locker = self
        own_ids = None
        own_locations = None

        if not is_admin:
           
            own_lockers = self.search([("active", "=", True)]) 
            own_ids = set(own_lockers.ids)
            own_locations = own_lockers.mapped("locker_location_id").filtered("create_3d_view")
            Locker = self.sudo()
            Location = Location.sudo()
            Site = Site.sudo()
            Company = Company.sudo()

        # ---- companies
        if is_admin:
            company_domain = []
            if company_id:
                company_domain.append(("id", "=", company_id))
            companies = Company.search(company_domain, order="name")
        else:
            companies = own_locations.mapped("company_id").sorted("name")
            if company_id:
                companies = companies.filtered(lambda c: c.id == company_id)

        # ---- locations
        location_domain = [("create_3d_view", "=", True)]
        if company_id:
            location_domain.append(("company_id", "=", company_id))
        if not is_admin:
            location_domain.append(("id", "in", own_locations.ids))
        locations = Location.search(location_domain, order="name")

        # ---- sites
        site_domain = [("active", "=", True)]
        if company_id:
            site_domain.append(("locker_location_id.company_id", "=", company_id))
        if not is_admin:
            site_domain.append(("locker_location_id", "in", own_locations.ids))
        sites = Site.search(site_domain, order="id")

        # ---- lockers
        locker_domain = [("active", "=", True)]
        if company_id:
            locker_domain.append(("company_id", "=", company_id))
        if not is_admin:
            locker_domain.append(("locker_location_id", "in", own_locations.ids))
        lockers = Locker.search(
            locker_domain,
            order="locker_location_id, site_id, profile_id, name, id",
        )

        profiles = self.env["locker.profile"].search([], order="name")
        if not is_admin:
            profiles = profiles & own_lockers.mapped("profile_id")

        status_colors = {
            company.id: {
                "available": company.available_locker_color or "#28A745",
                "allocated": company.allocated_locker_color or "#DC3545",
                "reserved": company.reserved_locker_color or "#FFC107",
            }
            for company in companies
        }

        def locker_payload(locker):
            is_mine = is_admin or locker.id in own_ids
            data = {
                "id": locker.id,
                "is_mine": is_mine,
                "company_id": locker.company_id.id,
                "locker_location_id": locker.locker_location_id.id,
                "site_id": locker.site_id.id if locker.site_id else False,
                "side": locker.side or "side_1",
                "pos_x": float(locker.pos_x or 0.0),
                "pos_y": float(locker.pos_y or 0.0),
                "pos_z": float(locker.pos_z or 0.0),
                "width": float(locker.width or 1.0),
                "height": float(locker.height or 1.0),
                "depth": float(locker.depth or 1.0),
                "w": float(locker.width or 1.0),
                "h": float(locker.height or 1.0),
                "d": float(locker.depth or 1.0),
            }
            if is_mine:
                data.update({
                    "name": locker.name,
                    "status": locker.status,
                    "locker_location": locker.locker_location_id.name or "",
                    "profile_id": locker.profile_id.id,
                    "profile_color": locker.profile_id.color,
                    "profile": locker.profile_id.name,
                    "color": locker.profile_id.color or "#198754",
                })
            else:
                data.update({
                    "name": "",
                    "status": locker.status,
                    "locker_location": "",
                    "profile_id": locker.profile_id.id,
                    "profile_color": locker.profile_id.color,
                    "profile": "",
                    "color": locker.profile_id.color or "#198754",
                })
            return data

        return {
            "status_colors": status_colors,
            "current_company_id": self.env.company.id,
            "companies": [
                {
                    "id": company.id,
                    "name": company.name,
                }
                for company in companies
            ],
            "locker_locations": [
                {
                    "id": location.id,
                    "name": location.name,
                    "company_id": location.company_id.id,
                }
                for location in locations
            ],
            "sites": [
                {
                    "id": site.id,
                    "name": site.name,
                    "width": float(site.width or 1.0),
                    "height": float(site.height or 1.0),
                    "depth": float(site.depth or 1.0),
                    "pos_x": float(site.pos_x or 0.0),
                    "pos_y": float(site.pos_y or 0.0),
                    "pos_z": float(site.pos_z or 0.0),
                    "active": site.active,
                    "locker_location_id": site.locker_location_id.id,
                    "company_id": site.company_id.id,
                }
                for site in sites
            ],
            "lockers": [locker_payload(locker) for locker in lockers],
            "profiles": [
                {
                    "id": profile.id,
                    "name": profile.name,
                    "color": profile.color or "#198754",
                }
                for profile in profiles
            ],
            "is_admin": is_admin,
        }

    @api.model
    def get_locker_locations(self, company_id):
        locations = self.env["locker.location"].search(
            [
                ("company_id", "=", company_id),
                ("create_3d_view", "=", True),
            ],
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
                ("state", "in", ("allocated", "renewal_pending", "expired")),
            ],
            order="id desc",
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


    @api.model
    def update_locker_position(self, locker_id, pos_x, pos_y, pos_z, side=None,site_id=None,):
        if not self.env.user.has_group("iPredict_locker_management.group_locker_admin"):
            raise AccessError(_("Only a Locker Administrator can change the 3D layout."))
        locker = self.browse(locker_id)
        if locker.exists():
            vals = {
                'pos_x': float(pos_x),
                'pos_y': float(pos_y),
                'pos_z': float(pos_z),
            }
            if side in ("side_1", "side_2"):
                vals['side'] = side

                        
            if site_id:
                vals["site_id"] = int(site_id)

            locker.write(vals)
            return True
        return False