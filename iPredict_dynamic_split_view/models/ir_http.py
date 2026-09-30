# -*- coding: utf-8 -*-

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()

        company = self.env.company
        res["enable_split_view"] = company.enable_split_view
        res["split_direction"] = company.split_direction
        res["enable_split_view_type"] = company.enable_split_view_type
        res["enable_list_split_view"] = company.enable_list_split_view
        res["enable_kanban_split_view"] = company.enable_kanban_split_view
        res["default_split_view"] = company.split_view_default
        res["enable_new_split_view"] = company.enable_new_split_view

        return res