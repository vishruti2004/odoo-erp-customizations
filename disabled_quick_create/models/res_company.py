# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    enable_restriction = fields.Boolean(string="Enable Restriction")
    restricted_model_ids = fields.Many2many(comodel_name="ir.model", string="Restricted Models", help="Select the models where the Create and Create & Edit options should be hidden. Leave empty to apply the restriction globally.")