from odoo import models

class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        res = super().session_info()
        company = self.env.company
        res["enable_list_split_view"] = company.enable_list_split_view
        res["enable_kanban_split_view"] = company.enable_kanban_split_view
        return res