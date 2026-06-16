from odoo import fields, models

class PosOrder(models.Model):
    _inherit = "pos.order"

    is_guest_queue_auto_assigned = fields.Boolean(string="Guest Queue Auto Assigned",default=False)