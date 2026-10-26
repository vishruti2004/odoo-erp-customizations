from odoo import api, fields, models


class PosPrepOrder(models.Model):
    _inherit = "pos.prep.order"

    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium", required=True,
        help="Copied from the PoS order when it is sent to the kitchen.")
    priority_updated_by = fields.Many2one("res.users")
    priority_updated_at = fields.Datetime()

    @api.model_create_multi
    def create(self, vals_list):
        """A ticket starts with the priority chosen on its PoS order."""
        for vals in vals_list:
            if "priority" not in vals and vals.get("pos_order_id"):
                order = self.env["pos.order"].browse(vals["pos_order_id"])
                if order.kitchen_priority:
                    vals["priority"] = order.kitchen_priority
        return super().create(vals_list)

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        """A cancelled PoS order never appears on the kitchen screens."""
        parent = getattr(super(), "_load_pos_preparation_data_domain", None)
        domain = parent(data) if parent else []
        extra = [("pos_order_id.state", "!=", "cancel")]
        if not domain:
            return extra
        return list(domain) + extra  # two prefix domains one after the other = AND

    def _kitchen_displays(self):
        return self.prep_line_ids.state_ids.stage_id.prep_display_id

    def _kitchen_apply_priority(self, priority):
        """Write the priority and push it to every display holding one of the tickets."""
        now = fields.Datetime.now()
        self.write({
            "priority": priority,
            "priority_updated_by": self.env.user.id,
            "priority_updated_at": now,
        })
        payload = {
            "prep_order_ids": self.ids, "priority": priority,
            "updated_at": fields.Datetime.to_string(now),
        }
        for display in self._kitchen_displays():
            display._notify("PRIORITY_CHANGED", payload)