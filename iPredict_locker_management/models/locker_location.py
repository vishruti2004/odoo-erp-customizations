# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class LockerLocation(models.Model):
    _name = "locker.location"
    _description = "Locker Location"
    _rec_name = "name"
    _order = "name"

    name = fields.Char(string="Locker Location", required=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(string="Active", default=True)
    partner_id = fields.Many2one("res.partner", string="Responsible Person")
    site_ids = fields.One2many("locker.site", "locker_location_id", string="Sites")
    locker_config_ids = fields.One2many("locker.location.line", "location_id", string="Locker Configurations")
    total_lockers = fields.Integer(string="Total Lockers", compute="_compute_total_lockers")
    available_lockers = fields.Integer(string="Available Lockers", compute="_compute_locker_statistics")
    allocated_lockers = fields.Integer(string="Allocated Lockers", compute="_compute_locker_statistics")
    locker_profile_ids = fields.Many2many("locker.profile", string="Locker Profiles", compute="_compute_locker_profile_ids")
    locker_profile_tags_html = fields.Html(string="Locker Profiles", compute="_compute_locker_profile_tags_html", sanitize=False)
    available_percentage = fields.Float(string="Available Percentage", compute="_compute_locker_statistics")
    allocated_percentage = fields.Float(string="Allocated Percentage", compute="_compute_locker_statistics")
    create_3d_view = fields.Boolean(string="Create 3D View", default=False)
    show_3d_view_option = fields.Boolean(string="Show 3D View Option", related="company_id.enable_3d_locker_view", readonly=True)

    def action_open_3d_view(self):
        self.ensure_one()

        if not self.company_id.enable_3d_locker_view:
            raise UserError("3D Locker View is disabled in Locker Management Settings.")

        if not self.create_3d_view:
            raise UserError("3D View has not been created for this locker location.")

        return {
            "type": "ir.actions.client",
            "tag": "locker_3d_view",
            "name": f"3D View - {self.name}",
            "target": "current",
            "context": {
                "default_location_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def _compute_total_lockers(self):
        Locker = self.env["locker.locker"]
        for location in self:
            location.total_lockers = Locker.search_count([
                ("locker_location_id", "=", location.id),
            ])

    @api.depends("site_ids.line_ids.profile_id")
    def _compute_locker_profile_ids(self):
        for location in self:
            location.locker_profile_ids = location.site_ids.mapped("line_ids.profile_id")

    @api.depends(
        "site_ids.line_ids.profile_id",
        "site_ids.line_ids.profile_id.name",
        "site_ids.line_ids.profile_id.color",
    )
    def _compute_locker_profile_tags_html(self):
        for location in self:
            profiles = location.site_ids.mapped("line_ids.profile_id")
            tags = []

            for profile in profiles:
                color = profile.color or "#6C757D"
                tags.append(
                    f"""
                    <span style="
                        display:inline-block;
                        background-color:{color};
                        color:#ffffff;
                        padding:3px 9px;
                        margin:2px 3px 2px 0;
                        border-radius:12px;
                        font-size:12px;
                        font-weight:500;
                        line-height:1.3;
                        white-space:nowrap;
                    ">
                        {profile.name}
                    </span>
                    """
                )

            location.locker_profile_tags_html = "".join(tags)

    def _compute_locker_statistics(self):
        Locker = self.env["locker.locker"]

        for location in self:
            lockers = Locker.search([
                ("locker_location_id", "=", location.id),
            ])

            total = len(lockers)
            available = len(lockers.filtered(lambda locker: locker.status == "available"))
            allocated = len(lockers.filtered(lambda locker: locker.status == "allocated"))

            location.available_lockers = available
            location.allocated_lockers = allocated

            if total:
                location.available_percentage = (available / total) * 100
                location.allocated_percentage = (allocated / total) * 100
            else:
                location.available_percentage = 0.0
                location.allocated_percentage = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    def action_generate_lockers(self):
        for location in self:
            location.site_ids.action_generate_lockers()
        return True

    def action_view_available_lockers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Available Lockers",
            "res_model": "locker.locker",
            "view_mode": "list,form",
            "domain": [
                ("locker_location_id", "=", self.id),
                ("status", "=", "available"),
            ],
            "context": {
                "default_locker_location_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_view_allocated_lockers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Allocated Lockers",
            "res_model": "locker.locker",
            "view_mode": "list,form",
            "domain": [
                ("locker_location_id", "=", self.id),
                ("status", "=", "allocated"),
            ],
            "context": {
                "default_locker_location_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

    def action_view_lockers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Lockers",
            "res_model": "locker.locker",
            "view_mode": "list,form",
            "domain": [("locker_location_id", "=", self.id)],
            "context": {
                "default_locker_location_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }


class LockerSite(models.Model):
    _name = "locker.site"
    _description = "Locker Site"
    _rec_name = "name"
    _order = "sequence, name"

    name = fields.Char(string="Site", required=True)
    sequence = fields.Integer(string="Sequence", default=10)
    locker_location_id = fields.Many2one("locker.location", string="Locker Location", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", string="Company", related="locker_location_id.company_id", store=True, readonly=True)
    active = fields.Boolean(string="Active", default=True)
    note = fields.Text(string="Notes")
    width = fields.Float(string="Width", default=1.0, required=True)
    height = fields.Float(string="Height", default=1.0, required=True)
    depth = fields.Float(string="Depth", default=1.0, required=True)
    pos_x = fields.Float(string="Position X", default=0.0)
    pos_y = fields.Float(string="Position Y", default=0.0)
    pos_z = fields.Float(string="Position Z", default=0.0)
    line_ids = fields.One2many("locker.location.line", "site_id", string="Locker Types")
    total_lockers = fields.Integer(string="Total Lockers", compute="_compute_total_lockers", store=True)

    @api.depends("line_ids.quantity")
    def _compute_total_lockers(self):
        for site in self:
            site.total_lockers = sum(site.line_ids.mapped("quantity"))

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    def action_generate_lockers(self):
        Locker = self.env["locker.locker"]

        for site in self:
            if not site.locker_location_id:
                continue

            location_sites = self.search([
                ("locker_location_id", "=", site.locker_location_id.id),
                ("active", "=", True),
            ])

            if not location_sites:
                continue

            min_site_x = min(location_sites.mapped("pos_x")) - (max(location_sites.mapped("width") or [1.0]) / 2)
            max_site_x = max(location_sites.mapped("pos_x")) + (max(location_sites.mapped("width") or [1.0]) / 2)
            min_site_z = min(location_sites.mapped("pos_z")) - (max(location_sites.mapped("depth") or [1.0]) / 2)
            max_site_z = max(location_sites.mapped("pos_z")) + (max(location_sites.mapped("depth") or [1.0]) / 2)

            center_x = (min_site_x + max_site_x) / 2
            center_z = (min_site_z + max_site_z) / 2

            delta_x = site.pos_x - center_x
            delta_z = site.pos_z - center_z

            orientation = "vertical" if abs(delta_x) >= abs(delta_z) else "horizontal"

            site_min_x = site.pos_x - site.width / 2
            site_min_y = site.pos_y
            site_min_z = site.pos_z - site.depth / 2
            site_max_x = site.pos_x + site.width / 2
            site_max_y = site.pos_y + site.height
            site_max_z = site.pos_z + site.depth / 2

            existing_lockers = Locker.search(
                [
                    ("locker_location_id", "=", site.locker_location_id.id),
                    ("site_id", "=", site.id),
                ],
                order="id asc",
            )

            target_lockers_payload = []

            for line in site.line_ids:
                width = float(line.width or 1.0)
                height = float(line.height or 1.0)
                depth = float(line.depth or 1.0)

                rows = max(int(line.rows or 1), 1)
                cols = max(int(line.cols or 1), 1)
                levels = max(int(line.levels or 1), 1)

                start_row = max(int(line.start_row or 1), 1)
                start_col = max(int(line.start_col or 1), 1)

                side = line.side or "side_1"

                required_height = (start_row - 1) * height + (rows * height)

                if orientation == "vertical":
                    required_line_length = (start_col - 1) * depth + (cols * depth)
                    available_line_length = site.depth
                else:
                    required_line_length = (start_col - 1) * width + (cols * width)
                    available_line_length = site.width

                required_depth = depth * levels

                if required_line_length > available_line_length + 0.0001:
                    raise UserError(
                        "Locker configuration does not fit inside %s.\n\n"
                        "Orientation: %s\n"
                        "Side: %s\n"
                        "Required Line Length: %.2f\n"
                        "Available Line Length: %.2f\n"
                        "Locker Profile: %s"
                        % (
                            site.name,
                            "Vertical" if orientation == "vertical" else "Horizontal",
                            "Side 1" if side == "side_1" else "Side 2",
                            required_line_length,
                            available_line_length,
                            line.profile_id.name,
                        )
                    )

                if required_height > site.height + 0.0001:
                    raise UserError(
                        "Locker configuration does not fit inside %s.\n\n"
                        "Orientation: %s\n"
                        "Side: %s\n"
                        "Required Height: %.2f\n"
                        "Available Height: %.2f\n"
                        "Locker Profile: %s"
                        % (
                            site.name,
                            "Vertical" if orientation == "vertical" else "Horizontal",
                            "Side 1" if side == "side_1" else "Side 2",
                            required_height,
                            site.height,
                            line.profile_id.name,
                        )
                    )

                if required_depth > site.depth + 0.0001:
                    raise UserError(
                        "Locker configuration does not fit inside %s.\n\n"
                        "Side: %s\n"
                        "Required Depth: %.2f\n"
                        "Available Depth: %.2f\n"
                        "Locker Profile: %s"
                        % (
                            site.name,
                            "Side 1" if side == "side_1" else "Side 2",
                            required_depth,
                            site.depth,
                            line.profile_id.name,
                        )
                    )

                for row in range(rows):
                    for column in range(cols):
                        for level in range(levels):
                            local_y = (start_row - 1 + row) * height

                            if orientation == "horizontal":
                                local_x = (start_col - 1 + column) * width
                                pos_x = site_min_x + local_x
                                pos_y = site_min_y + local_y

                                if side == "side_1":
                                    pos_z = site.pos_z - ((level + 1) * depth)
                                else:
                                    pos_z = site.pos_z + (level * depth)
                            else:
                                local_z = (start_col - 1 + column) * depth
                                pos_y = site_min_y + local_y
                                pos_z = site_min_z + local_z

                                if side == "side_1":
                                    pos_x = site.pos_x - ((level + 1) * depth)
                                else:
                                    pos_x = site.pos_x + (level * depth)

                            if orientation == "horizontal":
                                locker_min_x = pos_x
                                locker_max_x = pos_x + width
                                locker_min_z = pos_z
                                locker_max_z = pos_z + depth
                            else:
                                locker_min_x = pos_x
                                locker_max_x = pos_x + depth
                                locker_min_z = pos_z
                                locker_max_z = pos_z + depth

                            locker_min_y = pos_y
                            locker_max_y = pos_y + height

                            if locker_min_x < (site.pos_x - site.width / 2) - 0.0001:
                                raise UserError("Locker exceeds the left boundary of %s." % site.name)

                            if locker_max_x > (site.pos_x + site.width / 2) + 0.0001:
                                raise UserError("Locker exceeds the right boundary of %s." % site.name)

                            if locker_min_y < site_min_y - 0.0001:
                                raise UserError("Locker exceeds the bottom boundary of %s." % site.name)

                            if locker_max_y > site_max_y + 0.0001:
                                raise UserError("Locker exceeds the height boundary of %s." % site.name)

                            if locker_min_z < site_min_z - 0.0001:
                                raise UserError("Locker exceeds the back boundary of %s." % site.name)

                            if locker_max_z > site_max_z + 0.0001:
                                raise UserError("Locker exceeds the front boundary of %s." % site.name)

                            target_lockers_payload.append({
                                "profile_id": line.profile_id.id,
                                "company_id": site.company_id.id,
                                "locker_location_id": site.locker_location_id.id,
                                "site_id": site.id,
                                "side": side,
                                "pos_x": pos_x,
                                "pos_y": pos_y,
                                "pos_z": pos_z,
                                "width": width,
                                "height": height,
                                "depth": depth,
                                "status": "available",
                            })

                existing_count = len(existing_lockers)
                target_count = len(target_lockers_payload)

                for index in range(min(existing_count, target_count)):
                    existing_lockers[index].write(target_lockers_payload[index])

                if target_count > existing_count:
                    Locker.create(target_lockers_payload[existing_count:])
                elif existing_count > target_count:
                    lockers_to_remove = existing_lockers[target_count:]
                    allocated_lockers = lockers_to_remove.filtered(lambda locker: locker.status != "available")

                    if allocated_lockers:
                        raise UserError(
                            "Cannot reduce locker quantity! Some lockers are currently in use: %s"
                            % ", ".join(allocated_lockers.mapped("name"))
                        )

                    lockers_to_remove.unlink()

        return True

    def action_view_lockers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Lockers - {self.name}",
            "res_model": "locker.locker",
            "view_mode": "list,form",
            "domain": [("site_id", "=", self.id)],
            "context": {
                "default_site_id": self.id,
                "default_locker_location_id": self.locker_location_id.id,
                "default_company_id": self.company_id.id,
            },
        }


class LockerLocationLine(models.Model):
    _name = "locker.location.line"
    _description = "Locker Location Line"

    site_id = fields.Many2one("locker.site", string="Site", required=True, ondelete="cascade")
    location_id = fields.Many2one("locker.location", string="Locker Location", ondelete="cascade")
    side = fields.Selection([("side_1", "Side 1"), ("side_2", "Side 2")], string="Side", default="side_1", required=True, index=True)
    profile_id = fields.Many2one("locker.profile", string="Locker Profile", required=True)
    width = fields.Float(string="Width", default=1.0, required=True)
    height = fields.Float(string="Height", default=2.0, required=True)
    depth = fields.Float(string="Depth", default=1.0, required=True)
    start_row = fields.Integer(string="Start Row", default=1, required=True)
    start_col = fields.Integer(string="Start Column", default=1, required=True)
    rows = fields.Integer(string="Rows", default=1, required=True)
    cols = fields.Integer(string="Cols", default=5, required=True)
    levels = fields.Integer(string="Levels", default=1, required=True)
    quantity = fields.Integer(string="Total Lockers", compute="_compute_quantity", store=True)

    @api.constrains("site_id", "location_id")
    def _check_site_location(self):
        for line in self:
            if line.site_id and line.location_id and line.site_id.locker_location_id != line.location_id:
                raise UserError("The selected Site must belong to the selected Locker Location.")

    @api.depends("rows", "cols", "levels")
    def _compute_quantity(self):
        for line in self:
            line.quantity = (line.rows or 1) * (line.cols or 1) * (line.levels or 1)

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def write(self, vals):
        return super().write(vals)

    def unlink(self):
        return super().unlink()