from odoo import api, fields, models

class RepairOrder(models.Model):
    _inherit = "repair.order"

    equipment_id = fields.Many2one("maintenance.equipment", string="Equipment", domain="[('product_id', '=', product_id)]")

    @api.onchange("equipment_id")
    def _onchange_equipment_id(self):
        if self.equipment_id and self.equipment_id.product_id:
            self.product_id = self.equipment_id.product_id