from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    kitchen_advanced = fields.Boolean(
        "Advanced Kitchen", help="Enable station routing, order priority, chef assignment, order readiness and "
                                 "workload balancing on the preparation displays.")
    kitchen_strict_chef_station = fields.Boolean(
        "Restrict chefs to their stations", default=True,
        help="Only allow chefs to be assigned to items of the stations they work on.")
    kitchen_auto_assign = fields.Selection(
        [("manual", "Manual Assignment"), ("auto", "Automatic Assignment")],
        string="Assignment mode", default="manual", required=True,
        help="Manual Assignment: chefs take items on the kitchen screen.\n"
             "Dynamic Automatic Assignment: each new item is sent to the least busy station of its category "
             "and assigned to an available chef, sharing the work fairly. Manual changes are always kept.")
    kitchen_balance_tolerance = fields.Float(
        "Similar workload", default=2.0,
        help="Workloads within this difference are treated as equal, so the work is shared in turns. "
             "Counted in items for Item Wise stations and in minutes for Time Wise stations.")

    def _kitchen_auto(self):
        self.ensure_one()
        return bool(self.kitchen_advanced and self.kitchen_auto_assign == "auto")

    @api.model
    def _load_pos_data_fields(self, *args, **kwargs):
        fields_list = super()._load_pos_data_fields(*args, **kwargs)
        return fields_list + ["kitchen_advanced"] if fields_list else fields_list
