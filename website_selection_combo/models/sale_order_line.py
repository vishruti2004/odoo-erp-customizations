# -*- coding: utf-8 -*-
from odoo import api, fields, models
import json

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    combo_details = fields.Text(
        string="Combo Details",
        copy=False,
    )
    is_combo_line = fields.Boolean(
        string="Is Combo Line",
        compute="_compute_is_combo_line",
        store=True,
    )

    @api.depends('combo_details')
    def _compute_is_combo_line(self):
        for line in self:
            line.is_combo_line = bool(line.combo_details)

    def get_combo_items(self):
        if not self.combo_details:
            return []
        try:
            return json.loads(self.combo_details)
        except:
            return []

    def set_combo_items(self, items):
        self.combo_details = json.dumps(items) if items else False