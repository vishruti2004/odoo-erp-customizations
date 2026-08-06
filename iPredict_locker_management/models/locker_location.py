# -*- coding: utf-8 -*-

from odoo import api, fields, models


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

    @api.depends("line_ids.quantity")
    def _compute_total_lockers(self):
        for rec in self:
            rec.total_lockers = sum(rec.line_ids.mapped("quantity"))

    @api.model_create_multi
    def create(self, vals_list):
        records = super(LockerLocation, self).create(vals_list)
        for rec in records:
            rec.action_generate_lockers()
        return records

    def write(self, vals):
        res = super(LockerLocation, self).write(vals)
        for rec in self:
            rec.action_generate_lockers()
        return res

    def action_generate_lockers(self):
        for location in self:
            Locker = self.env["locker.locker"]
            lockers_to_create = []
            GAP = 0.08

            for line in location.line_ids:
                w = line.width or 1.0
                h = line.height or 1.0
                d = line.depth or 1.0

                rows = line.rows or 1
                cols = line.cols or 1
                levels = line.levels or 1

                start_row = line.start_row or 1
                start_col = line.start_col or 1

                for r in range(rows):
                    for c in range(cols):
                        for l in range(levels):
                            pos_x = (start_col - 1 + c) * (w + GAP)
                            pos_y = (start_row - 1 + r) * (h + GAP)
                            pos_z = l * (d + GAP)

                            lockers_to_create.append({
                                "profile_id": line.profile_id.id,
                                "company_id": location.company_id.id,
                                "locker_location_id": location.id,
                                "status": "available",
                                "pos_x": pos_x,
                                "pos_y": pos_y,
                                "pos_z": pos_z,
                                "width": w,
                                "height": h,
                                "depth": d,
                            })

            existing = Locker.search([
                ("locker_location_id", "=", location.id)
            ])
            if existing:
                existing.unlink()

            if lockers_to_create:
                Locker.create(lockers_to_create)

        return True


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

    @api.depends("rows", "cols", "levels")
    def _compute_quantity(self):
        for line in self:
            line.quantity = (line.rows or 1) * (line.cols or 1) * (line.levels or 1)

    @api.model_create_multi
    def create(self, vals_list):
        records = super(LockerLocationLine, self).create(vals_list)
        for rec in records:
            if rec.location_id:
                rec.location_id.action_generate_lockers()
        return records

    def write(self, vals):
        res = super(LockerLocationLine, self).write(vals)
        for line in self:
            if line.location_id:
                line.location_id.action_generate_lockers()
        return res

    def unlink(self):
        locations = self.mapped("location_id")
        res = super(LockerLocationLine, self).unlink()
        for location in locations:
            location.action_generate_lockers()
        return res