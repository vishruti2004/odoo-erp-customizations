from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    kitchen_advanced = fields.Boolean(
        "Advanced Kitchen", help="Enables station routing, priority, chefs, readiness, analytics and workload "
                                 "on the preparation displays. Off = native behaviour.")
    kitchen_strict_chef_station = fields.Boolean(
        "Restrict chefs to their stations", default=True,
        help="Block assigning a chef to a station he does not work on.")
    kitchen_auto_assign = fields.Selection(
        [("manual", "Manual Assignment"), ("auto", "Dynamic Automatic Assignment")],
        string="Assignment mode", default="manual", required=True,
        help="Manual Assignment: the first station of the category gets the item and the kitchen assigns "
             "the chefs (Take / Assign chef).\n"
             "Dynamic Automatic Assignment: every new item goes to the category-compatible station with the "
             "lowest projected workload (using the Item Wise or Time Wise metric of each station) and to an "
             "eligible chef of that station, with a fair turn between chefs. Manual choices are never "
             "overwritten and stay available.")
    kitchen_balance_tolerance = fields.Float(
        "Similar workload", default=2.0,
        help="Workloads that differ by no more than this are considered equal and the fair turn decides. "
             "Expressed in the unit of the station metric: items (Item Wise) or minutes (Time Wise).")

    def _kitchen_auto(self):
        """Dynamic Automatic Assignment is active on this Point of Sale."""
        self.ensure_one()
        return bool(self.kitchen_advanced and self.kitchen_auto_assign == "auto")

    @api.model
    def _load_pos_data_fields(self, *args, **kwargs):
        fields_list = super()._load_pos_data_fields(*args, **kwargs)
        return fields_list + ["kitchen_advanced"] if fields_list else fields_list
