from odoo import fields, models

REPREP_REASONS = [
    ("wrong_item", "Wrong item prepared"),
    ("cooking", "Not cooked properly"),
    ("temperature", "Food is cold / wrong temperature"),
    ("quality", "Poor quality or presentation"),
    ("complaint", "Customer complaint"),
    ("other", "Other"),
]


class PosKitchenAssignmentHistory(models.Model):
    _name = "pos.kitchen.assignment.history"
    _description = "Kitchen Assignment History"
    _order = "changed_at desc, id desc"

    prep_line_id = fields.Many2one("pos.prep.line", ondelete="set null", index=True)
    pos_order_id = fields.Many2one("pos.order", string="PoS Order", ondelete="set null")
    order_name = fields.Char("Order")
    product_id = fields.Many2one("product.product", string="Product", ondelete="set null")
    previous_chef_id = fields.Many2one("pos.kitchen.chef", string="Previous chef", ondelete="set null")
    new_chef_id = fields.Many2one("pos.kitchen.chef", string="New chef", ondelete="set null")
    previous_station_id = fields.Many2one("pos.kitchen.station", string="From station", ondelete="set null")
    new_station_id = fields.Many2one("pos.kitchen.station", string="To station", ondelete="set null")
    move_type = fields.Selection(
        [("assign", "Chef assigned"), ("reassign", "Chef changed"), ("station_move", "Moved to another station")],
        string="Change", required=True)
    changed_by_chef_id = fields.Many2one("pos.kitchen.chef", string="Done by", ondelete="set null")
    changed_at = fields.Datetime("Date", default=fields.Datetime.now)
    reason = fields.Text()


class PosKitchenItemHistory(models.Model):
    _name = "pos.kitchen.item.history"
    _description = "Kitchen Item History"
    _order = "changed_at desc, id desc"

    prep_line_id = fields.Many2one("pos.prep.line", ondelete="set null", index=True)
    pos_order_id = fields.Many2one("pos.order", string="PoS Order", ondelete="set null")
    order_name = fields.Char("Order")
    product_id = fields.Many2one("product.product", string="Product", ondelete="set null")
    event_type = fields.Selection(string="Change", selection=[
        ("qty_increased", "Quantity increased"), ("qty_decreased", "Quantity decreased"),
        ("cancelled", "Cancelled"), ("reprep", "Re-prepare"),
    ], required=True)
    old_quantity = fields.Float("Quantity before")
    new_quantity = fields.Float("Quantity after")
    reason_type = fields.Selection(REPREP_REASONS, string="Reason")
    reason = fields.Char("Details", help="Reason of the re-prepare (the text typed when 'Other' is chosen).")
    chef_id = fields.Many2one("pos.kitchen.chef", string="Requested by", ondelete="set null")
    station_id = fields.Many2one("pos.kitchen.station", string="Station", ondelete="set null")
    changed_at = fields.Datetime("Date", default=fields.Datetime.now)
