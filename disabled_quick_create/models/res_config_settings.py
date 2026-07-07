# -*- coding: utf-8 -*-

from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_restriction = fields.Boolean(string="Enable Restriction", related="company_id.enable_restriction", readonly=False)
    restricted_model_ids = fields.Many2many(comodel_name="ir.model", string="Restricted Models", related="company_id.restricted_model_ids", readonly=False)

    @api.model
    def get_restriction_config(self):
        company = self.env.company

        return {
            "enable_restriction": company.enable_restriction,
            "restricted_model_ids": company.restricted_model_ids.mapped("model"),
        }