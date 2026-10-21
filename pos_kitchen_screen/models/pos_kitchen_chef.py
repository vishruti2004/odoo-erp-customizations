
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosKitchenChef(models.Model):
    _name = "pos.kitchen.chef"
    _description = "Kitchen Chef"
    _inherit = ["pos.load.mixin"]
    _order = "user_id, id"
    _rec_name = "user_id"

    user_id = fields.Many2one(
        "res.users",
        string="User",
        required=True,
        domain=[("share", "=", False)],
        ondelete="cascade",
    )

    station_ids = fields.Many2many(
        "pos.kitchen.station",
        string="Kitchen Stations",
        help="Kitchen stations this user can work on.",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(default=True)

    name = fields.Char(related="user_id.name", string="Name")

    allowed_station_ids = fields.Json(
        compute="_compute_allowed_station_ids",
    )

    @api.depends("station_ids")
    def _compute_allowed_station_ids(self):
        for chef in self:
            chef.allowed_station_ids = chef.station_ids.ids

    @api.constrains("station_ids", "company_id")
    def _check_station_company(self):
        for chef in self:
            if chef.station_ids.company_id - chef.company_id:
                raise ValidationError(
                    _("A chef can only work on stations belonging to the same company.")
                )

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [("active", "=", True)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return [
            "id",
            "name",
            "allowed_station_ids",
        ]
