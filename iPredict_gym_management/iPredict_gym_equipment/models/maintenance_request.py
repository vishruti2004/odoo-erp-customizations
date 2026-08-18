# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    repair_order_id = fields.Many2one("repair.order", string="Repair Order", readonly=True, copy=False)
    is_request_done = fields.Boolean(related="stage_id.done", string="Request Done", readonly=True)

    @api.constrains("company_id", "equipment_id")
    def _check_equipment_company(self):
        for request in self:
            if request.equipment_id and request.equipment_id.company_id != request.company_id:
                raise ValidationError(_("The Maintenance Equipment and Maintenance Request must belong to the same company."))

    def action_create_repair_request(self):
        self.ensure_one()

        if not self.equipment_id:
            raise ValidationError(_("Please select an Equipment before creating a Repair Order."))

        if self.equipment_id.company_id != self.company_id:
            raise ValidationError(_("The selected Equipment belongs to another company. Please select Equipment from the current company."))

        if not self.equipment_id.product_id:
            raise ValidationError(_("No Product is configured for the selected Equipment."))

        repair_order = self.env["repair.order"].with_company(self.company_id).create({
            "product_id": self.equipment_id.product_id.id,
            "equipment_id": self.equipment_id.id,
            "company_id": self.company_id.id,
        })

        self.repair_order_id = repair_order.id

        return {
            "type": "ir.actions.act_window",
            "name": _("Repair Order"),
            "res_model": "repair.order",
            "view_mode": "form",
            "res_id": repair_order.id,
            "target": "current",
        }