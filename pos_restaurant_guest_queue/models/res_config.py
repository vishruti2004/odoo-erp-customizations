from odoo import fields, models

class PosConfig(models.Model):
    _inherit = "pos.config"

    auto_assign_waiting_guest = fields.Boolean(string="Auto Assign Waiting Guest")
    waiting_duration = fields.Integer(string="Waiting Duration", default=5)

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_config_id = fields.Many2one("pos.config", string="Point of Sale", config_parameter="pos.config_id")
    auto_assign_waiting_guest = fields.Boolean(related="pos_config_id.auto_assign_waiting_guest", readonly=False)
    waiting_duration = fields.Integer(related="pos_config_id.waiting_duration", readonly=False)