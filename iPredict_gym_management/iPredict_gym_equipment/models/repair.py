# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RepairOrder(models.Model):
    _inherit = "repair.order"

    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Equipment",
        domain="[('product_id', '=', product_id), ('company_id', '=', company_id)]",
    )

    @api.onchange("equipment_id")
    def _onchange_equipment_id(self):
        if self.equipment_id:
            if self.equipment_id.company_id != self.company_id:
                self.equipment_id = False
                return {
                    "warning": {
                        "title": _("Company Mismatch"),
                        "message": _("Please select Equipment belonging to the same company."),
                    }
                }

            if self.equipment_id.product_id:
                self.product_id = self.equipment_id.product_id

    @api.constrains("equipment_id", "company_id")
    def _check_equipment_company(self):
        for repair in self:
            if repair.equipment_id and repair.equipment_id.company_id != repair.company_id:
                raise ValidationError(_("The Equipment and Repair Order must belong to the same company."))