# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    product_id = fields.Many2one("product.product", string="Product", ondelete="restrict")
    repair_order_ids = fields.One2many("repair.order", "equipment_id", string="Repair Orders")
    repair_order_count = fields.Integer(string="Repair Orders Count", compute="_compute_repair_order_count")

    @api.depends("repair_order_ids")
    def _compute_repair_order_count(self):
        for record in self:
            record.repair_order_count = len(record.repair_order_ids)

    def action_view_repair_orders(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Repair Orders"),
            "res_model": "repair.order",
            "view_mode": "list,form",
            "domain": [("equipment_id", "=", self.id), ("company_id", "=", self.company_id.id)],
            "context": {
                "default_equipment_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }