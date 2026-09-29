# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_split_view = fields.Boolean(
        related="company_id.enable_split_view",
        readonly=False,
        help="Enable Split View across the application for this company.",
    )

    split_view_default = fields.Boolean(
        related="company_id.split_view_default",
        readonly=False,
        help="Automatically open supported List and Kanban views in Split View.",
    )

    enable_list_split_view = fields.Boolean(
        related="company_id.enable_list_split_view",
        readonly=False,
        help="Allow records in List views to be opened in the Split View panel.",
    )

    enable_kanban_split_view = fields.Boolean(
        related="company_id.enable_kanban_split_view",
        readonly=False,
        help="Allow records in Kanban views to be opened in the Split View panel.",
    )

    split_horizontal = fields.Boolean(
        related="company_id.split_horizontal",
        readonly=False,
        help="Display the record panel beside the List or Kanban view.",
    )

    split_vertical = fields.Boolean(
        related="company_id.split_vertical",
        readonly=False,
        help="Display the record panel below the List or Kanban view.",
    )

    enable_new_split_view = fields.Boolean(
        related="company_id.enable_new_split_view",
        readonly=False,
        help="Open new records directly in the Split View panel instead of a full-page form.",
    )