# -*- coding: utf-8 -*-

from odoo import fields, models

class StockLocation(models.Model):
    _inherit = "stock.location"

    # 3D Position — where this location sits inside the warehouse space
    pos_x = fields.Float(string="Position X", default=0.0)
    pos_y = fields.Float(string="Position Y", default=0.0)
    pos_z = fields.Float(string="Position Z", default=0.0)

    # 3D Dimension — the size of the box representing this location/zone
    width = fields.Float(string="Width", default=4.0)
    height = fields.Float(string="Height", default=2.0)
    depth = fields.Float(string="Depth", default=4.0)