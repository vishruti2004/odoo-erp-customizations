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
    line_ids = fields.One2many("locker.location.line", "location_id", string="Locker Types")
    total_lockers = fields.Integer(string="Total Lockers", compute="_compute_total_lockers", store=True)
    partner_id = fields.Many2one(
    "res.partner",
    string="Responsible person",)

    def action_open_3d_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'locker_3d_view',
            'name': f'3D View - {self.name}',
            'target': 'current',
            'context': {
                'default_location_id': self.id,
                'default_company_id': self.company_id.id,
            }
        }

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
            GAP = 0.08

            existing_lockers = Locker.search([("locker_location_id", "=", location.id)], order="id asc")
            target_lockers_payload = []

            for line in location.line_ids:
                w, h, d = line.width or 1.0, line.height or 1.0, line.depth or 1.0
                rows, cols, levels = line.rows or 1, line.cols or 1, line.levels or 1
                start_row, start_col = line.start_row or 1, line.start_col or 1

                for r in range(rows):
                    for c in range(cols):
                        for l in range(levels):
                            pos_x = (start_col - 1 + c) * (w + GAP)
                            pos_y = (start_row - 1 + r) * (h + GAP)
                            pos_z = l * (d + GAP)

                            target_lockers_payload.append({
                                "profile_id": line.profile_id.id,
                                "company_id": location.company_id.id,
                                "locker_location_id": location.id,
                                "pos_x": pos_x,
                                "pos_y": pos_y,
                                "pos_z": pos_z,
                                "width": w,
                                "height": h,
                                "depth": d,
                            })

            existing_count = len(existing_lockers)
            target_count = len(target_lockers_payload)

            # Update existing lockers without deleting them
            for index in range(min(existing_count, target_count)):
                existing_lockers[index].write(target_lockers_payload[index])

            # Create new lockers if count increased
            if target_count > existing_count:
                new_payloads = target_lockers_payload[existing_count:]
                for payload in new_payloads:
                    payload["status"] = "available"
                Locker.create(new_payloads)

            # Safely remove excess lockers if count decreased
            elif existing_count > target_count:
                lockers_to_remove = existing_lockers[target_count:]
                allocated = lockers_to_remove.filtered(lambda l: l.status != "available")
                if allocated:
                    raise UserError(
                        f"Cannot reduce locker quantity! Some lockers are currently in use: "
                        f"{', '.join(allocated.mapped('name'))}"
                    )
                lockers_to_remove.unlink()

        return True


class LockerLocationLine(models.Model):
    _name = "locker.location.line"
    _description = "Locker Location Line"

    location_id = fields.Many2one("locker.location", string="Locker Location", required=True, ondelete="cascade")
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