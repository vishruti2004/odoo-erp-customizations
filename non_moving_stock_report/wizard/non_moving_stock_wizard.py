# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class NonMovingStockWizard(models.TransientModel):
    _name = "non.moving.stock.wizard"
    _description = "Non-Moving Stock Wizard"

    days = fields.Integer(string="Days", required=True)

    @api.constrains("days")
    def _check_days(self):
        for wizard in self:
            if wizard.days < 0:
                raise ValidationError(_("Days cannot be negative."))

    def action_open_report(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("non_moving_stock_report.action_non_moving_stock")

        start_date = fields.Date.today() - timedelta(days=self.days)

        action["context"] = {
            "non_moving_cutoff": fields.Date.to_string(start_date),
            "search_default_filter_non_moving": 1,
        }
        return action