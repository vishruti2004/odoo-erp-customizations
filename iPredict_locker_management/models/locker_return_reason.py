# -*- coding: utf-8 -*-

from odoo import fields, models


class LockerReturnReason(models.Model):
    _name = "locker.return.reason"
    _description = "Locker Return Reason"
    _order = "name"

    name = fields.Char(
        string="Reason",
        required=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
    )

    active = fields.Boolean(
        string="Active",
        default=True,
    )

    allocation_ids = fields.One2many(
        "locker.allocation",
        "return_reason_id",
        string="Locker Allocations",
    )