from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    kitchen_advanced = fields.Boolean(
        "Advanced Kitchen", help="Enables station routing, priority, chefs, readiness, analytics and workload "
                                 "on the preparation displays. Off = native behaviour.")
    kitchen_strict_chef_station = fields.Boolean(
        "Restrict chefs to their stations", default=True,
        help="Block assigning a chef to a station he does not work on.")

    @api.model
    def _load_pos_data_fields(self, *args, **kwargs):
        fields_list = super()._load_pos_data_fields(*args, **kwargs)
        return fields_list + ["kitchen_advanced"] if fields_list else fields_list
