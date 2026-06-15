from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo import SUPERUSER_ID
from odoo.modules.registry import Registry
import re
import threading
import time
from itertools import combinations

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
    table_ids = fields.Many2many("restaurant.table", "pos_guest_queue_table_rel", "guest_id", "table_id", string="Assigned Tables")
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
        records = super().create(vals_list)
        config = self.env['pos.config'].search([('module_pos_restaurant', '=', True)], limit=1)
        if config and config.auto_assign_waiting_guest:
            records.auto_assign_all_waiting_guests()
        return records

    def _get_available_tables(self):
        session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        if not session:
            return []
        floor_ids = session.config_id.floor_ids.ids
        all_tables = self.env["restaurant.table"].search([('floor_id', 'in', floor_ids)])
        available = []
        for table in all_tables:
            active_orders = self.env["pos.order"].search([("table_id", "=", table.id), ("state", "=", "draft")], limit=1)
            if not active_orders:
                available.append({
                    "id": table.id,
                    "seats": table.seats or 0,
                    "table_number": table.table_number,
                    "floor_id": table.floor_id.id,
                })
        return available

    def _select_best_tables(self, available_tables, party_size, current_floor_id=None):
        if not current_floor_id:
            session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
            if session and session.config_id.floor_ids:
                current_floor_id = session.config_id.floor_ids[0].id
        floor_tables = {}
        for table in available_tables:
            floor_id = table.get("floor_id")
            if not floor_id:
                floor_id = self.env["restaurant.table"].browse(table["id"]).floor_id.id
            floor_tables.setdefault(floor_id, []).append(table)
        floor_order = []
        if current_floor_id:
            floor_order.append(current_floor_id)
        floor_order.extend([f for f in floor_tables.keys() if f != current_floor_id])
        for floor_id in floor_order:
            tables = floor_tables.get(floor_id)
            if not tables or sum(t["seats"] for t in tables) < party_size:
                continue
            exact_match = [t for t in tables if t["seats"] == party_size]
            if exact_match:
                return [exact_match[0]]
            best_combination = None
            minimal_waste = float("inf")
            minimal_table_count = float("inf")
            for r in range(1, len(tables) + 1):
                for combination in combinations(tables, r):
                    total_seats = sum(t["seats"] for t in combination)
                    if total_seats < party_size:
                        continue
                    waste = total_seats - party_size
                    if waste < minimal_waste or (waste == minimal_waste and len(combination) < minimal_table_count):
                        best_combination = list(combination)
                        minimal_waste = waste
                        minimal_table_count = len(combination)
            if best_combination:
                return best_combination
        return []

    @api.model
    def check_table_has_notified_guest(self, table_ids):
        if not table_ids:
            return False
        guest = self.search([('state', '=', 'notified'), ('table_ids', 'in', table_ids)], limit=1)
        return bool(guest)

    @api.model
    def start_timer_for_guest(self, guest_id, table_ids, duration_minutes):
        def _timer_function():
            time.sleep(duration_minutes * 60)
            try:
                db_name = self.env.cr.dbname
                with Registry(db_name).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    guest = env['pos.guest.queue'].browse(guest_id)
                    if not guest.exists() or guest.state != 'notified':
                        return
                    has_order = False
                    for table in guest.table_ids:
                        orders = env['pos.order'].search([('table_id', '=', table.id), ('state', '=', 'draft'), ('partner_id', '=', guest.partner_id.id)])
                        if any(order.lines for order in orders):
                            has_order = True
                            break
                    if has_order:
                        guest.write({'state': 'seated'})
                    else:
                        guest.write({'state': 'cancelled', 'table_id': False, 'table_ids': [(5, 0, 0)]})
                        for table_id in table_ids:
                            env['pos.order'].search([('table_id', '=', table_id), ('state', '=', 'draft'), ('lines', '=', False)]).unlink()
            except Exception:
                pass
        threading.Thread(target=_timer_function, daemon=True).start()
        return True

    @api.model
    def auto_assign_all_waiting_guests(self):
        session = self.env['pos.session'].search([('state', '=', 'opened')], limit=1)
        if not session:
            return []
        config = self.env['pos.config'].search([('module_pos_restaurant', '=', True)], limit=1)
        waiting_duration = config.waiting_duration or 5
        current_floor_id = session.config_id.floor_ids[0].id if session.config_id.floor_ids else None
        assigned_guests = []
        while True:
            available_tables = self._get_available_tables()
            if not available_tables:
                break
            total_available_seats = sum(t["seats"] for t in available_tables)
            guest = self.search([("state", "=", "waiting"), ("party_size", "<=", total_available_seats)], order="arrival_time asc", limit=1)
            if not guest:
                break
            selected_tables = self._select_best_tables(available_tables, guest.party_size, current_floor_id)
            if not selected_tables:
                break
            table_ids = [t["id"] for t in selected_tables]
            partner = guest.partner_id
            if not partner:
                partner = self.env['res.partner'].create({'name': guest.guest_name, 'phone': guest.phone})
                guest.write({'partner_id': partner.id})
            guest.write({"state": "notified", "table_id": table_ids[0], "table_ids": [(6, 0, table_ids)]})
            for table_id in table_ids:
                self.env['pos.order'].create({'session_id': session.id, 'table_id': table_id, 'state': 'draft', 'partner_id': partner.id})
            self.start_timer_for_guest(guest.id, table_ids, waiting_duration)
            assigned_guests.append({"guest_id": guest.id, "guest_name": guest.guest_name, "waiting_list_id": guest.name, "party_size": guest.party_size, "table_ids": table_ids, "table_numbers": [t["table_number"] for t in selected_tables], "partner_id": partner.id, "waiting_duration": waiting_duration})
        return assigned_guests

    @api.model
    def get_available_tables_for_guest(self, party_size):
        party_size = int(party_size or 0)
        all_tables = self.env["restaurant.table"].search([])
        available_tables = []
        for table in all_tables:
            active_orders = self.env["pos.order"].search([("table_id", "=", table.id), ("state", "=", "draft")], limit=1)
            if not active_orders:
                available_tables.append({"id": table.id, "seats": table.seats or 0, "table_number": table.table_number, "floor_name": table.floor_id.name})
        if not available_tables:
            return {"type": "none", "tables": []}
        if party_size == 0:
            return {"type": "single", "tables": available_tables}
        exact_fit = [t for t in available_tables if t["seats"] == party_size]
        if exact_fit:
            return {"type": "single", "tables": exact_fit}
        larger_tables = [t for t in available_tables if (t["seats"] or 0) > party_size]
        if larger_tables:
            min_seats = min(t["seats"] for t in larger_tables)
            next_size_up = [t for t in larger_tables if t["seats"] == min_seats]
            return {"type": "single", "tables": next_size_up}
        total_available = sum(t["seats"] or 0 for t in available_tables)
        if total_available >= party_size:
            return {"type": "combination", "tables": available_tables}
        return {"type": "none", "tables": []}

    @api.model
    def find_best_guest_for_tables(self, available_table_ids):
        tables = self.env["restaurant.table"].browse(available_table_ids)
        total_seats = sum(t.seats or 0 for t in tables)
        guests = self.search([("state", "=", "waiting"), ("party_size", "<=", total_seats)], order="arrival_time asc", limit=1)
        if not guests:
            return None
        return {"id": guests.id, "waiting_list_id": guests.name, "guest_name": guests.guest_name, "party_size": guests.party_size}

    @api.model
    def assign_guest_to_table(self, guest_id, table_ids):
        if isinstance(table_ids, int):
            table_ids = [table_ids]
        guest = self.browse(guest_id)
        partner = guest.partner_id
        if not partner:
            partner = self.env['res.partner'].create({'name': guest.guest_name, 'phone': guest.phone})
            guest.write({'partner_id': partner.id})
        guest.write({"state": "notified", "table_id": table_ids[0], "table_ids": [(6, 0, table_ids)]})
        return partner.id

    @api.model
    def mark_guest_seated(self, guest_id):
        guest = self.browse(guest_id)
        if guest.state == "notified":
            guest.write({"state": "seated"})
        return True

    @api.model
    def cancel_guest_notification(self, guest_id):
        guest = self.browse(guest_id)
        guest.write({"state": "cancelled", "table_id": False, "table_ids": [(5, 0, 0)]})
        return True

    @api.model
    def check_guest_status(self, guest_id):
        return self.browse(guest_id).state

    @api.model
    def find_notified_guest_by_partner(self, partner_id):
        guest = self.search([("state", "=", "notified"), ("partner_id", "=", partner_id)], limit=1)
        return {"id": guest.id, "guest_name": guest.guest_name} if guest else None

    @api.model
    def get_pos_config(self):
        config = self.env['pos.config'].search([('module_pos_restaurant', '=', True)], limit=1)
        return {"auto_assign": config.auto_assign_waiting_guest, "waiting_duration": config.waiting_duration or 5}