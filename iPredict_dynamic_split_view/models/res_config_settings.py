# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_list_split_view = fields.Boolean(
        related="company_id.enable_list_split_view",
        readonly=False,
    )

    enable_kanban_split_view = fields.Boolean(
        related="company_id.enable_kanban_split_view",
        readonly=False,
    )

    