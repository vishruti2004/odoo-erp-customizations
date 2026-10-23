from odoo import api, fields, models


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    station_ids = fields.One2many("pos.kitchen.station", "prep_display_id", string="Kitchen Stations")
    kitchen_advanced = fields.Boolean(
        compute="_compute_kitchen_advanced",
        help="True when a linked Point of Sale enabled the advanced kitchen.")

    @api.depends("pos_config_ids.kitchen_advanced")
    def _compute_kitchen_advanced(self):
        for display in self:
            display.kitchen_advanced = any(display._get_pos_config_ids().mapped("kitchen_advanced"))

    def _load_preparation_data_models(self):
        return super()._load_preparation_data_models() + ["pos.kitchen.station", "pos.kitchen.chef"]

    def _kitchen_displays_for_orders(self, pos_orders):
        states = self.env["pos.prep.state"].search([
            ("prep_line_id.prep_order_id.pos_order_id", "in", pos_orders.ids)])
        return states.stage_id.prep_display_id
