from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import re

class PosGuestQueue(models.Model):
    _name = "pos.guest.queue"
    _description = "POS Guest Queue"
    _order = "arrival_time asc"

    name = fields.Char(string="Waiting List ID", required=True, copy=False, readonly=True, default="New")
    guest_name = fields.Char(string="Guest Name", required=True)
    phone = fields.Char(string="Phone Number", required=True)
    party_size = fields.Integer(string="Party Size", required=True)
    arrival_time = fields.Datetime(string="Arrival Time", default=fields.Datetime.now, readonly=True)
    state = fields.Selection([("waiting", "Waiting"), ("seated", "Seated"), ("cancelled", "Cancelled")], string="Status", default="waiting", readonly=True)
    table_id = fields.Many2one("restaurant.table", string="Assigned Table", readonly=True)

    @api.constrains('phone')
    def _check_phone_number(self):
        for record in self:
            if record.phone and not re.match(r'^\d{10}$', record.phone):
                raise ValidationError(_("Phone number must be exactly 10 digits."))

    @api.constrains('party_size')
    def _check_party_size(self):
        for record in self:
            if record.party_size <= 0:
                raise ValidationError(_("Party size must be a positive number greater than 0."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("pos.guest.queue") or "New"
        return super().create(vals_list)

    @api.model
    def get_eligible_guest_data(self, seats):
        guests = self.search([("state", "=", "waiting"), ("party_size", "<=", seats)], order="arrival_time asc")
        return [
            {
                "id": guest.id,
                "waiting_list_id": guest.name,
                "guest_name": guest.guest_name,
                "party_size": guest.party_size,
            }
            for guest in guests
        ]

    @api.model
    def assign_guest_to_table(self, guest_id, table_id):
        guest = self.browse(guest_id)
        guest.write({"state": "seated", "table_id": table_id})
        return True