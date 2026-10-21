from odoo import fields, models


class PosKitchenAssignmentHistory(models.Model):
    _name = "pos.kitchen.assignment.history"
    _description = "Kitchen Assignment History"
    _order = "changed_at desc, id desc"

    prep_line_id = fields.Many2one("pos.prep.line", ondelete="set null", index=True)
    pos_order_id = fields.Many2one("pos.order", ondelete="set null")
    product_id = fields.Many2one("product.product", ondelete="set null")
    previous_chef_id = fields.Many2one("pos.kitchen.chef", ondelete="set null")
    new_chef_id = fields.Many2one("pos.kitchen.chef", ondelete="set null")
    previous_station_id = fields.Many2one("pos.kitchen.station", ondelete="set null")
    new_station_id = fields.Many2one("pos.kitchen.station", ondelete="set null")
    move_type = fields.Selection(
        [("assign", "Assign"), ("reassign", "Reassign chef"), ("station_move", "Station move")], required=True)
    changed_by = fields.Many2one("res.users", default=lambda self: self.env.user)
    changed_by_chef_id = fields.Many2one("pos.kitchen.chef", ondelete="set null")
    changed_at = fields.Datetime(default=fields.Datetime.now)
    reason = fields.Text()


class PosKitchenItemHistory(models.Model):
    _name = "pos.kitchen.item.history"
    _description = "Kitchen Item History"
    _order = "changed_at desc, id desc"

    prep_order_id = fields.Many2one("pos.prep.order", ondelete="set null")
    prep_line_id = fields.Many2one("pos.prep.line", ondelete="set null", index=True)
    pos_order_id = fields.Many2one("pos.order", ondelete="set null")
    product_id = fields.Many2one("product.product", ondelete="set null")
    event_type = fields.Selection([
        ("new_item", "New item"), ("qty_increased", "Quantity increased"),
        ("qty_decreased", "Quantity decreased"), ("cancelled", "Cancelled"),
        ("note_changed", "Note changed"), ("reprep", "Re-prepare"),
    ], required=True)
    old_quantity = fields.Float()
    new_quantity = fields.Float()
    changed_by = fields.Many2one("res.users", default=lambda self: self.env.user)
    changed_by_chef_id = fields.Many2one("pos.kitchen.chef", ondelete="set null")
    changed_at = fields.Datetime(default=fields.Datetime.now)
    notes = fields.Text()
