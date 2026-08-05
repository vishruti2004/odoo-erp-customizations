# -*- coding: utf-8 -*-

from odoo import fields, models,api


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

    quantity = fields.Integer(
        string="Lockers",
        default=1,
        required=True,
    )