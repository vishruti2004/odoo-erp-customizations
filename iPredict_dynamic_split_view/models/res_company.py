# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    enable_split_view = fields.Boolean(
        string="Enable Split View",
        default=False,
        help="Enable Split View functionality for supported List and Kanban views.",
    )

    split_direction = fields.Selection(
        [
            ("horizontal", "Horizontal"),
            ("vertical", "Vertical"),
            ("both", "Both"),
        ],
        string="Split View Type",
        default="horizontal",
        help="Choose the Split View orientation available to users.",
    )

    enable_split_view_type = fields.Boolean(
        string="Enable Split View Type",
        default=False,
        help="Enable Split View for selected List and Kanban views.",
    )

    enable_list_split_view = fields.Boolean(
        string="List View",
        default=False,
        help="Enable Split View for List views.",
    )

    enable_kanban_split_view = fields.Boolean(
        string="Kanban View",
        default=False,
        help="Enable Split View for Kanban views.",
    )

    split_view_default = fields.Boolean(
        string="Default Split View",
        default=False,
        help="Open supported List and Kanban views with Split View enabled by default.",
    )

    enable_new_split_view = fields.Boolean(
        string="New Record in Split View",
        default=False,
        help="Open newly created records directly in the Split View panel instead of a full-page form.",
    )