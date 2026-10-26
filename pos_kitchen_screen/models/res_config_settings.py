from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_kitchen_advanced = fields.Boolean(related="pos_config_id.kitchen_advanced", readonly=False)
    pos_kitchen_auto_assign = fields.Selection(related="pos_config_id.kitchen_auto_assign", readonly=False)
