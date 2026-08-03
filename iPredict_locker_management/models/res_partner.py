# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    locker_allocation_ids = fields.One2many("locker.allocation", "partner_id", string="Locker Allocations")
    has_active_locker = fields.Boolean(compute="_compute_has_active_locker")

    @api.depends("locker_allocation_ids.state")
    def _compute_has_active_locker(self):
        for rec in self:
            rec.has_active_locker = any(
                allocation.state == "allocated"
                for allocation in rec.locker_allocation_ids
            )