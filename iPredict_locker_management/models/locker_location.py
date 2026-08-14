# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError


class LockerLocation(models.Model):
    _name = "locker.location"
    _description = "Locker Location"
    _rec_name = "name"
    _order = "name"

    name = fields.Char(
        string="Locker Location",
        required=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(
        string="Active",
        default=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Responsible Person",
    )

    line_ids = fields.One2many(
        "locker.location.line",
        "location_id",
        string="Locker Types",
    )

    total_lockers = fields.Integer(
        string="Total Lockers",
        compute="_compute_total_lockers",
        store=True,
    )

    available_lockers = fields.Integer(
        string="Available Lockers",
        compute="_compute_locker_statistics",
    )

    allocated_lockers = fields.Integer(
        string="Allocated Lockers",
        compute="_compute_locker_statistics",
    )

    locker_profile_ids = fields.Many2many(
        "locker.profile",
        string="Locker Profiles",
        compute="_compute_locker_profile_ids",
    )

    locker_profile_tags_html = fields.Html(
        string="Locker Profiles",
        compute="_compute_locker_profile_tags_html",
        sanitize=False,
    )

    available_percentage = fields.Float(
        string="Available Percentage",
        compute="_compute_locker_statistics",
    )

    allocated_percentage = fields.Float(
        string="Allocated Percentage",
        compute="_compute_locker_statistics",
    )

    # ============================================================
    # 3D VIEW
    # ============================================================

    def action_open_3d_view(self):
        self.ensure_one()

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

    # ============================================================
    # TOTAL LOCKERS
    # ============================================================

    @api.depends("line_ids.quantity")
    def _compute_total_lockers(self):
        for location in self:
            location.total_lockers = sum(
                location.line_ids.mapped("quantity")
            )

    # ============================================================
    # LOCKER PROFILES
    # ============================================================

    @api.depends("line_ids.profile_id")
    def _compute_locker_profile_ids(self):
        for location in self:
            location.locker_profile_ids = location.line_ids.mapped(
                "profile_id"
            )

    # ============================================================
    # LOCKER PROFILE COLORED TAGS
    # ============================================================

    @api.depends(
        "line_ids.profile_id",
        "line_ids.profile_id.name",
        "line_ids.profile_id.color",
    )
    def _compute_locker_profile_tags_html(self):
        for location in self:
            profiles = location.line_ids.mapped("profile_id")

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

    # ============================================================
    # LOCKER STATISTICS
    # ============================================================

    def _compute_locker_statistics(self):
        Locker = self.env["locker.locker"]

        for location in self:
            lockers = Locker.search([
                ("locker_location_id", "=", location.id),
            ])

            total = len(lockers)

            available = len(
                lockers.filtered(
                    lambda locker: locker.status == "available"
                )
            )

            allocated = len(
                lockers.filtered(
                    lambda locker: locker.status == "allocated"
                )
            )

            location.available_lockers = available
            location.allocated_lockers = allocated

            if total:
                location.available_percentage = (
                    available / total
                ) * 100

                location.allocated_percentage = (
                    allocated / total
                ) * 100
            else:
                location.available_percentage = 0.0
                location.allocated_percentage = 0.0

    # ============================================================
    # CREATE
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for location in records:
            location.action_generate_lockers()

        return records

    # ============================================================
    # WRITE
    # ============================================================

    def write(self, vals):
        result = super().write(vals)

        for location in self:
            location.action_generate_lockers()

        return result

    # ============================================================
    # GENERATE LOCKERS
    # ============================================================

    def action_generate_lockers(self):
        for location in self:

            Locker = self.env["locker.locker"]

            GAP = 0.08

            existing_lockers = Locker.search(
                [
                    ("locker_location_id", "=", location.id),
                ],
                order="id asc",
            )

            target_lockers_payload = []

            for line in location.line_ids:

                width = line.width or 1.0
                height = line.height or 1.0
                depth = line.depth or 1.0

                rows = line.rows or 1
                cols = line.cols or 1
                levels = line.levels or 1

                start_row = line.start_row or 1
                start_col = line.start_col or 1

                for row in range(rows):

                    for column in range(cols):

                        for level in range(levels):

                            pos_x = (
                                (start_col - 1 + column)
                                * (width + GAP)
                            )

                            pos_y = (
                                (start_row - 1 + row)
                                * (height + GAP)
                            )

                            pos_z = (
                                level
                                * (depth + GAP)
                            )

                            target_lockers_payload.append({
                                "profile_id": line.profile_id.id,
                                "company_id": location.company_id.id,
                                "locker_location_id": location.id,
                                "pos_x": pos_x,
                                "pos_y": pos_y,
                                "pos_z": pos_z,
                                "width": width,
                                "height": height,
                                "depth": depth,
                            })

            existing_count = len(existing_lockers)
            target_count = len(target_lockers_payload)

            # ----------------------------------------------------
            # UPDATE EXISTING LOCKERS
            # ----------------------------------------------------

            for index in range(
                min(existing_count, target_count)
            ):
                existing_lockers[index].write(
                    target_lockers_payload[index]
                )

            # ----------------------------------------------------
            # CREATE NEW LOCKERS
            # ----------------------------------------------------

            if target_count > existing_count:

                new_payloads = target_lockers_payload[
                    existing_count:
                ]

                for payload in new_payloads:
                    payload["status"] = "available"

                Locker.create(new_payloads)

            # ----------------------------------------------------
            # REMOVE EXCESS LOCKERS
            # ----------------------------------------------------

            elif existing_count > target_count:

                lockers_to_remove = existing_lockers[
                    target_count:
                ]

                allocated_lockers = lockers_to_remove.filtered(
                    lambda locker: locker.status != "available"
                )

                if allocated_lockers:
                    raise UserError(
                        "Cannot reduce locker quantity! Some lockers "
                        "are currently in use: %s"
                        % ", ".join(
                            allocated_lockers.mapped("name")
                        )
                    )

                lockers_to_remove.unlink()

        return True

    def action_view_lockers(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Lockers",
            "res_model": "locker.locker",
            "view_mode": "list,form",
            "domain": [
                ("locker_location_id", "=", self.id)
            ],
            "context": {
                "default_locker_location_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }

# =================================================================
# LOCKER LOCATION LINE
# =================================================================

class LockerLocationLine(models.Model):
    _name = "locker.location.line"
    _description = "Locker Location Line"

    location_id = fields.Many2one(
        "locker.location",
        string="Locker Location",
        required=True,
        ondelete="cascade",
    )

    profile_id = fields.Many2one(
        "locker.profile",
        string="Locker Profile",
        required=True,
    )

    width = fields.Float(
        string="Width",
        default=1.0,
        required=True,
    )

    height = fields.Float(
        string="Height",
        default=2.0,
        required=True,
    )

    depth = fields.Float(
        string="Depth",
        default=1.0,
        required=True,
    )

    start_row = fields.Integer(
        string="Start Row",
        default=1,
        required=True,
    )

    start_col = fields.Integer(
        string="Start Column",
        default=1,
        required=True,
    )

    rows = fields.Integer(
        string="Rows",
        default=1,
        required=True,
    )

    cols = fields.Integer(
        string="Cols",
        default=5,
        required=True,
    )

    levels = fields.Integer(
        string="Levels",
        default=1,
        required=True,
    )

    quantity = fields.Integer(
        string="Total Lockers",
        compute="_compute_quantity",
        store=True,
    )

    # ============================================================
    # QUANTITY
    # ============================================================

    @api.depends(
        "rows",
        "cols",
        "levels",
    )
    def _compute_quantity(self):
        for line in self:
            line.quantity = (
                (line.rows or 1)
                * (line.cols or 1)
                * (line.levels or 1)
            )

    # ============================================================
    # CREATE
    # ============================================================

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        for line in records:
            if line.location_id:
                line.location_id.action_generate_lockers()

        return records

    # ============================================================
    # WRITE
    # ============================================================

    def write(self, vals):
        result = super().write(vals)

        for line in self:
            if line.location_id:
                line.location_id.action_generate_lockers()

        return result

    # ============================================================
    # UNLINK
    # ============================================================

    def unlink(self):
        locations = self.mapped("location_id")

        result = super().unlink()

        for location in locations:
            location.action_generate_lockers()

        return result

