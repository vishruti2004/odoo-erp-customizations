# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    enable_split_view = fields.Boolean(
        string="Enable Split ",
        default=False,
        help="Enable Split View across the application for this company.",
    )

    split_view_default = fields.Boolean(
        string="Default Split View",
        default=False,
        help="Automatically open supported List and Kanban views in Split View.",
    )

    enable_list_split_view = fields.Boolean(
        string="Enable List View",
        default=False,
        help="Allow records in List views to be opened in the Split View panel.",
    )

    enable_kanban_split_view = fields.Boolean(
        string="Enable Kanban View",
        default=False,
        help="Allow records in Kanban views to be opened in the Split View panel.",
    )

    split_horizontal = fields.Boolean(
        string="Horizontal",
        default=False,
        help="Display the record panel beside the List or Kanban view.",
    )

    split_vertical = fields.Boolean(
        string="Vertical",
        default=False,
        help="Display the record panel below the List or Kanban view.",
    )

    enable_new_split_view = fields.Boolean(
        string="Enable New Record in Split View",
        default=False,
        help="Open new records directly in the Split View panel instead of a full-page form.",
    )