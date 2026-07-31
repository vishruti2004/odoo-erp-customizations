from odoo import fields, models

class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    repair_order_id = fields.Many2one(
        "repair.order",
        string="Repair Order",
        readonly=True,
        copy=False,
    )

    is_request_done = fields.Boolean(
        related="stage_id.done",
        string="Request Done",
        readonly=True,
    )

    def action_create_repair_request(self):
        self.ensure_one()

        # If repair order already exists, open it
        # if self.repair_order_id:
        #     return {
        #         "type": "ir.actions.act_window",
        #         "name": ("Repair Order"),
        #         "res_model": "repair.order",
        #         "view_mode": "form",
        #         "res_id": self.repair_order_id.id,
        #         "target": "current",
        #     }

        repair_order = self.env["repair.order"].create({
            "product_id": self.equipment_id.product_id.id,
            "equipment_id": self.equipment_id.id,
        })

        self.repair_order_id = repair_order.id

        return {
            "type": "ir.actions.act_window",
            "name": ("Repair Order"),
            "res_model": "repair.order",
            "view_mode": "form",
            "res_id": repair_order.id,
            "target": "current",
        }