# -*- coding: utf-8 -*-

from odoo import api, models

class ResUsers(models.Model):
    _inherit = "res.users"

    @api.model
    def check_advanced_chatter_access(self):
        return self.env.user.has_group(
            "advanced_chatter.group_advanced_chatter_user"
        )