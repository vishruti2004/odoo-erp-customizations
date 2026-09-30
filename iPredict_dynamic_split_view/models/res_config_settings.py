# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_split_view = fields.Boolean(
        related="company_id.enable_split_view",
        readonly=False,
        help="Enable Split View functionality for supported List and Kanban views.",
    )

    split_direction = fields.Selection(
        related="company_id.split_direction",
        readonly=False,
        help="Choose the Split View orientation available to users.",
    )

    enable_split_view_type = fields.Boolean(
        related="company_id.enable_split_view_type",
        readonly=False,
        help="Enable Split View for selected List and Kanban views.",
    )

    enable_list_split_view = fields.Boolean(
        related="company_id.enable_list_split_view",
        readonly=False,
        help="Enable Split View for List views.",
    )

    enable_kanban_split_view = fields.Boolean(
        related="company_id.enable_kanban_split_view",
        readonly=False,
        help="Enable Split View for Kanban views.",
    )

    split_view_default = fields.Boolean(
        related="company_id.split_view_default",
        readonly=False,
        help="Open supported List and Kanban views with Split View enabled by default.",
    )

    enable_new_split_view = fields.Boolean(
        related="company_id.enable_new_split_view",
        readonly=False,
        help="Open newly created records directly in the Split View panel instead of a full-page form.",
    )