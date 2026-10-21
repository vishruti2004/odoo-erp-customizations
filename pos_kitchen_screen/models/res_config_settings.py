from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_kitchen_advanced = fields.Boolean(related="pos_config_id.kitchen_advanced", readonly=False)
