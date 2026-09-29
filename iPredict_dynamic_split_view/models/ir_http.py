# -*- coding: utf-8 -*-

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()

        company = self.env.company

        # Global Configuration
        res["enable_split_view"] = company.enable_split_view
        res["default_split_view"] = company.split_view_default

        # List View Configuration
        res["enable_list_split_view"] = company.enable_list_split_view

        # Kanban View Configuration
        res["enable_kanban_split_view"] = company.enable_kanban_split_view

        # Split Direction Configuration
        res["split_horizontal"] = company.split_horizontal
        res["split_vertical"] = company.split_vertical

        # New Record Configuration
        res["enable_new_split_view"] = company.enable_new_split_view

        return res