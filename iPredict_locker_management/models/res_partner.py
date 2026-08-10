# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    locker_allocation_ids = fields.One2many("locker.allocation", "partner_id", string="Locker Allocations")
    has_active_locker = fields.Boolean(compute="_compute_has_active_locker")
    locker_pin = fields.Char(string="Locker PIN", copy=False)

    @api.depends("locker_allocation_ids.state")
    def _compute_has_active_locker(self):
        for partner in self:
            partner.has_active_locker = any(allocation.state == "allocated" for allocation in partner.locker_allocation_ids)

    def write(self, vals):
        locker_pin_changed = "locker_pin" in vals
        result = super().write(vals)

        if locker_pin_changed:
            for partner in self:
                credentials = self.env["locker.access.credential"].search([("partner_id", "=", partner.id), ("active", "=", True), ("allocation_id.state", "=", "allocated"), ("access_method", "=", "pin")], order="id desc", limit=1)
                if credentials:
                    credentials.write({"pin_code": partner.locker_pin or False})

        return result