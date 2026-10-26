from odoo import api, fields, models


class PosPrepDisplay(models.Model):
    _inherit = "pos.prep.display"

    station_ids = fields.One2many("pos.kitchen.station", "prep_display_id", string="Kitchen Stations")
    kitchen_advanced = fields.Boolean(
        compute="_compute_kitchen_advanced",
        help="True when a linked Point of Sale enabled the advanced kitchen.")
    kitchen_auto_assign = fields.Selection(
        [("manual", "Manual Assignment"), ("auto", "Dynamic Automatic Assignment")],
        compute="_compute_kitchen_advanced",
        help="Dynamic Automatic when one linked Point of Sale with the advanced kitchen uses it.")

    @api.depends("pos_config_ids.kitchen_advanced", "pos_config_ids.kitchen_auto_assign")
    def _compute_kitchen_advanced(self):
        for display in self:
            configs = display._get_pos_config_ids().filtered("kitchen_advanced")
            display.kitchen_advanced = bool(configs)
            display.kitchen_auto_assign = "auto" if "auto" in configs.mapped("kitchen_auto_assign") else "manual"

    @api.model
    def web_search_read(self, domain, specification, **kwargs):
        """Backend views: a chef sees only the preparation displays of his stations."""
        Station = self.env["pos.kitchen.station"]
        if not Station._kitchen_is_manager():
            domain = list(domain or []) + [("id", "in", Station._kitchen_user_chef().station_ids.prep_display_id.ids)]
        return super().web_search_read(domain, specification, **kwargs)

    def _load_preparation_data_models(self):
        return super()._load_preparation_data_models() + ["pos.kitchen.station", "pos.kitchen.chef"]

    def _kitchen_displays_for_orders(self, pos_orders):
        states = self.env["pos.prep.state"].search([
            ("prep_line_id.prep_order_id.pos_order_id", "in", pos_orders.ids)])
        return states.stage_id.prep_display_id
