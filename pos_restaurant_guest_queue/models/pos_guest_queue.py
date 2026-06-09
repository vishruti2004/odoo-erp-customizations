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
    state = fields.Selection([
        ("waiting", "Waiting"),
        ("notified", "Notified"),
        ("seated", "Seated"),
        ("cancelled", "Cancelled")
    ], string="Status", default="waiting", readonly=True)
    table_id = fields.Many2one("restaurant.table", string="Assigned Table", readonly=True)
    table_ids = fields.Many2many(
        "restaurant.table", 
        "pos_guest_queue_table_rel", 
        "guest_id", 
        "table_id", 
        string="Assigned Tables")
    partner_id = fields.Many2one('res.partner', string="Partner", readonly=True)

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
    def get_available_tables_for_guest(self, party_size):
        all_tables = self.env["restaurant.table"].search([])
        available_tables = []
        for table in all_tables:
            active_orders = self.env["pos.order"].search([
                ("table_id", "=", table.id),
                ("state", "=", "draft"),
            ], limit=1)
            if not active_orders:
                available_tables.append({
                    "id": table.id,
                    "name": f"Table {table.table_number}",
                    "seats": table.seats,
                    "table_number": table.table_number,
                    "floor_name": table.floor_id.name,
                })

        if not available_tables:
            return {"type": "none", "tables": []}

        if party_size == 0:
            return {"type": "single", "tables": available_tables}

        exact_fit = [t for t in available_tables if t["seats"] == party_size]
        if exact_fit:
            return {"type": "single", "tables": exact_fit}

        larger = [t for t in available_tables if t["seats"] > party_size]
        if larger:
            min_seats = min(t["seats"] for t in larger)
            next_size_up = [t for t in larger if t["seats"] == min_seats]
            return {"type": "single", "tables": next_size_up}

        total_available = sum(t["seats"] for t in available_tables)
        if total_available >= party_size:
            return {"type": "combination", "tables": available_tables}

        return {"type": "none", "tables": []}

    @api.model
    def find_best_guest_for_tables(self, available_table_ids):
        tables = self.env["restaurant.table"].browse(available_table_ids)
        total_seats = sum(t.seats for t in tables)
        guests = self.search([
            ("state", "=", "waiting"),
            ("party_size", "<=", total_seats),
        ], order="arrival_time asc", limit=1)

        if not guests:
            return None

        return {
            "id": guests.id,
            "waiting_list_id": guests.name,
            "guest_name": guests.guest_name,
            "party_size": guests.party_size,
        }

    @api.model
    def find_table_combination(self, available_tables, guest_party_size):
        sorted_tables = sorted(available_tables, key=lambda t: t["seats"], reverse=True)
        total_seats = sum(t["seats"] for t in available_tables)

        if total_seats < guest_party_size:
            return None

        best_combo = []
        remaining = guest_party_size

        for table in sorted_tables:
            if remaining <= 0:
                break
            best_combo.append(table)
            remaining -= table["seats"]

        return best_combo

    @api.model
    def assign_guest_to_table(self, guest_id, table_ids):
        if isinstance(table_ids, int):
            table_ids = [table_ids]
        guest = self.browse(guest_id)

        partner = guest.partner_id
        if not partner:
            partner = self.env['res.partner'].create({
                'name': guest.guest_name,
                'phone': guest.phone,
            })
            guest.write({'partner_id': partner.id})

        guest.write({
            "state": "seated",
            "table_id": table_ids[0],
            "table_ids": [(6, 0, table_ids)],
        })

        return partner.id  

    @api.model
    def cancel_guest_notification(self, guest_id):
        guest = self.browse(guest_id)
        guest.write({
            "state": "cancelled",
            "table_id": False,
        })
        return True

    @api.model
    def check_guest_status(self, guest_id):
        guest = self.browse(guest_id)
        return guest.state