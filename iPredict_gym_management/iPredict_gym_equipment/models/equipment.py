from odoo import api, fields, models

class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"

    product_id = fields.Many2one(
        "product.product",
        string="Product",
        ondelete="restrict",
    )

    repair_order_ids = fields.One2many(
        "repair.order",
        "equipment_id",
        string="Repair Orders",
    )
