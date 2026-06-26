# -*- coding: utf-8 -*-
from odoo import fields, models

class StockMove(models.Model):
    _inherit = "stock.move"

    workorder_id = fields.Many2one(
        'mrp.workorder',
        string='Work Order',
        help='Linked Work Order for phase-wise material management'
    )