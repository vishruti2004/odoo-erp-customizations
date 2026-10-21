from odoo import api, fields, models


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    station_ids = fields.One2many("pos.kitchen.station", "prep_display_id", string="Kitchen Stations")
    kitchen_advanced = fields.Boolean(compute="_compute_kitchen_advanced",
                                      help="True when at least one linked Point of Sale enabled the advanced kitchen.")

    ticket_density = fields.Selection(
        [("compact", "Compact"), ("normal", "Normal"), ("expanded", "Expanded")], default="normal", required=True)
    card_columns = fields.Integer("Card columns", default=0, help="0 = automatic")
    layout_mode = fields.Selection(
        [("grid", "Grid (native)"), ("list", "List"), ("lanes", "Lanes (one column per stage)")],
        default="grid", required=True)
    default_zoom = fields.Float(default=1.0)
    show_chef = fields.Boolean("Show chef", default=True)
    show_station = fields.Boolean("Show station", default=True)
    show_priority = fields.Boolean("Show priority", default=True)
    show_readiness = fields.Boolean("Show table readiness", default=True)
    show_workload = fields.Boolean("Show workload", default=True)
    change_highlight_minutes = fields.Integer("Highlight changes (min)", default=5)
    enable_shortcuts = fields.Boolean("Keyboard / touch shortcuts", default=True)
    chef_idle_minutes = fields.Integer("Chef idle logout (min)", default=0, help="0 = never")

    @api.depends("pos_config_ids.kitchen_advanced")
    def _compute_kitchen_advanced(self):
        for display in self:
            display.kitchen_advanced = any(display._get_pos_config_ids().mapped("kitchen_advanced"))

    def _load_preparation_data_models(self):
        models = super()._load_preparation_data_models()
        return models + ["pos.kitchen.station", "pos.kitchen.chef"]

    def _kitchen_displays_for_orders(self, pos_orders):
        states = self.env["pos.prep.state"].search([
            ("prep_line_id.prep_order_id.pos_order_id", "in", pos_orders.ids)])
        return states.stage_id.prep_display_id
