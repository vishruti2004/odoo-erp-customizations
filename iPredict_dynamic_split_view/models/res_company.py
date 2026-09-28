# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    enable_list_split_view = fields.Boolean(
        string="Enable List Split View",
        default=False,
    )

    enable_kanban_split_view = fields.Boolean(
        string="Enable Kanban Split View",
        default=False,
    )

