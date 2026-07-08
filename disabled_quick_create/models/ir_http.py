from odoo import models

class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        result = super().session_info()
        company = self.env.company
        result["quick_create_restriction"] = {
            "enabled": company.enable_restriction,
            "model_ids": company.restricted_model_ids.mapped("model"),
            "allowed_group_ids": company.allowed_group_ids.ids,
            "current_user_group_ids": self.env.user.group_ids.ids,
        }
        return result