from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo import SUPERUSER_ID
from odoo.modules.registry import Registry
import re
import threading
import time
from itertools import combinations
import logging

_logger = logging.getLogger(__name__)

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
    
    pos_session_id = fields.Many2one(
        'pos.session', string="Restaurant", 
        domain=[('state', '=', 'opened')], 
        compute="_compute_pos_session_id", 
        store=True, readonly=False
    )
    table_ids = fields.Many2many(
        "restaurant.table", "pos_guest_queue_table_rel", 
        "guest_id", "table_id", string="Assigned Tables"
    )
    partner_id = fields.Many2one('res.partner', string="Partner", readonly=True)
    has_multiple_sessions = fields.Boolean(string="Multiple Sessions Open", compute="_compute_has_multiple_sessions")

    @api.depends('pos_session_id')
    def _compute_has_multiple_sessions(self):
        opened_count = self.env['pos.session'].search_count([('state', '=', 'opened')])
        for record in self:
            record.has_multiple_sessions = opened_count > 1

    @api.depends('has_multiple_sessions')
    def _compute_pos_session_id(self):
        for record in self:
            if not record.pos_session_id:
                opened_sessions = self.env['pos.session'].search([('state', '=', 'opened')])
                if len(opened_sessions) == 1:
                    record.pos_session_id = opened_sessions[0].id

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
        opened_sessions = self.env['pos.session'].search([('state', '=', 'opened')])
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("pos.guest.queue") or "New"
            if not vals.get('pos_session_id') and len(opened_sessions) == 1:
                vals['pos_session_id'] = opened_sessions[0].id
        
        records = super().create(vals_list)
        for record in records:
            if record.pos_session_id and record.pos_session_id.config_id.auto_assign_waiting_guest:
                self.auto_assign_all_waiting_guests(session_id=record.pos_session_id.id)
        return records

    def _get_available_tables(self, session_id):
        session = self.env['pos.session'].browse(session_id)
        if not session.exists() or session.state != 'opened':
            return []
        
        all_tables = self.env["restaurant.table"].search([('floor_id', 'in', session.config_id.floor_ids.ids)])
        available = []
        for table in all_tables:
            active = self.env["pos.order"].search([("table_id", "=", table.id), ("state", "=", "draft"), ("session_id", "=", session_id)], limit=1)
            if not active:
                available.append({"id": table.id, "seats": table.seats or 0, "table_number": table.table_number, "floor_id": table.floor_id.id})
        return available

    def _select_best_tables(self, available_tables, party_size, session_id):
        session = self.env['pos.session'].browse(session_id)
        current_floor_id = session.config_id.floor_ids[0].id if session.config_id.floor_ids else None
        
        floor_tables = {}
        for table in available_tables:
            f_id = table.get("floor_id") or self.env["restaurant.table"].browse(table["id"]).floor_id.id
            floor_tables.setdefault(f_id, []).append(table)
            
        floor_order = [current_floor_id] if current_floor_id else []
        floor_order.extend([f for f in floor_tables.keys() if f != current_floor_id])
        
        for f_id in floor_order:
            tables = floor_tables.get(f_id)
            if not tables or sum(t["seats"] for t in tables) < party_size:
                continue
            
            exact = [t for t in tables if t["seats"] == party_size]
            if exact: return [exact[0]]
            
            best, min_waste, min_count = None, float("inf"), float("inf")
            for r in range(1, len(tables) + 1):
                for combo in combinations(tables, r):
                    total = sum(t["seats"] for t in combo)
                    if total < party_size: continue
                    waste = total - party_size
                    if waste < min_waste or (waste == min_waste and len(combo) < min_count):
                        best, min_waste, min_count = list(combo), waste, len(combo)
            if best: return best
        return []

    @api.model
    def start_timer_for_guest(self, guest_id, table_ids, duration_minutes, session_id):
        def _timer_function():
            time.sleep(duration_minutes * 60)
            try:
                with Registry(self.env.cr.dbname).cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    guest = env['pos.guest.queue'].browse(guest_id)
                    if not guest.exists() or guest.state != 'notified': return
                    
                    has_order = any(order.lines for table in guest.table_ids 
                                    for order in env['pos.order'].search([('table_id', '=', table.id), 
                                    ('state', '=', 'draft'), ('partner_id', '=', guest.partner_id.id)]))
                    
                    if has_order:
                        guest.write({'state': 'seated'})
                    else:
                        guest.write({'state': 'cancelled', 'table_ids': [(5, 0, 0)]})
                        env['pos.order'].search([('table_id', 'in', table_ids), ('state', '=', 'draft'), 
                                                 ('lines', '=', False)]).unlink()
                        session = env['pos.session'].browse(session_id)
                        if session.state == 'opened':
                            env['pos.guest.queue'].auto_assign_all_waiting_guests(session_id=session_id)
            except Exception as e: _logger.error(str(e))
        threading.Thread(target=_timer_function, daemon=True).start()
        return True

    @api.model
    def auto_assign_all_waiting_guests(self, session_id=None):
        if not session_id:
            return [res for session in self.env['pos.session'].search([('state', '=', 'opened')]) 
                    for res in self.auto_assign_all_waiting_guests(session_id=session.id)]
        
        session = self.env['pos.session'].browse(session_id)
        if session.state != 'opened': return []
        
        while True:
            avail = self._get_available_tables(session_id=session_id)
            if not avail: break
            guest = self.search([("state", "=", "waiting"), ("party_size", "<=", sum(t["seats"] for t in avail)), 
                                 ("pos_session_id", "=", session_id)], order="arrival_time asc", limit=1)
            if not guest: break
            
            selected = self._select_best_tables(avail, guest.party_size, session_id)
            if not selected: break
            
            t_ids = [t["id"] for t in selected]
            partner = guest.partner_id or self.env['res.partner'].create({'name': guest.guest_name, 'phone': guest.phone})
            if not guest.partner_id: guest.write({'partner_id': partner.id})
            
            guest.write({"state": "notified", "table_ids": [(6, 0, t_ids)]})
            for t_id in t_ids:
                self.env['pos.order'].create({'session_id': session_id, 'table_id': t_id, 'state': 'draft', 
                                              'partner_id': partner.id, 'is_guest_queue_auto_assigned': True})
            self.start_timer_for_guest(guest.id, t_ids, session.config_id.waiting_duration or 5, session_id=session_id)
        return True

    @api.model
    def get_available_tables_for_guest(self, party_size, session_id):
        session = self.env['pos.session'].browse(session_id)
        if session.state != 'opened': return {"type": "none", "tables": []}
        
        tables = self.env["restaurant.table"].search([('floor_id', 'in', session.config_id.floor_ids.ids)])
        avail = [{"id": t.id, "seats": t.seats or 0, "table_number": t.table_number, "floor_name": t.floor_id.name} 
                 for t in tables if not self.env["pos.order"].search([("table_id", "=", t.id), 
                 ("state", "=", "draft"), ("session_id", "=", session_id)], limit=1)]
        
        if not avail: return {"type": "none", "tables": []}
        if int(party_size or 0) == 0: return {"type": "single", "tables": avail}
        
        exact = [t for t in avail if t["seats"] == int(party_size)]
        if exact: return {"type": "single", "tables": exact}
        
        larger = [t for t in avail if t["seats"] > int(party_size)]
        if larger: return {"type": "single", "tables": [min(larger, key=lambda x: x['seats'])]}
        
        return {"type": "combination", "tables": avail} if sum(t["seats"] for t in avail) >= int(party_size) else {"type": "none", "tables": []}

    @api.model
    def find_best_guest_for_tables(self, available_table_ids, session_id):
        total = sum(t.seats or 0 for t in self.env["restaurant.table"].browse(available_table_ids))
        guest = self.search([("state", "=", "waiting"), ("party_size", "<=", total), ("pos_session_id", "=", session_id)], order="arrival_time asc", limit=1)
        return {"id": guest.id, "waiting_list_id": guest.name, "guest_name": guest.guest_name, "party_size": guest.party_size} if guest else None

    @api.model
    def assign_guest_to_table(self, guest_id, table_ids, session_id):
        if isinstance(table_ids, int): table_ids = [table_ids]
        guest = self.browse(guest_id)
        partner = guest.partner_id or self.env['res.partner'].create({'name': guest.guest_name, 'phone': guest.phone})
        guest.write({"state": "notified", "table_ids": [(6, 0, table_ids)], "pos_session_id": session_id, "partner_id": partner.id})
        return partner.id

    @api.model
    def mark_guest_seated(self, guest_id):
        self.browse(guest_id).filtered(lambda g: g.state == "notified").write({"state": "seated"})
        return True

    @api.model
    def find_notified_guest_by_partner(self, partner_id, session_id):
        guest = self.search([("state", "=", "notified"), ("partner_id", "=", partner_id), ("pos_session_id", "=", session_id)], limit=1)
        return {"id": guest.id, "guest_name": guest.guest_name} if guest else None

    @api.model
    def get_pos_config(self):
        sessions = self.env['pos.session'].search([('state', '=', 'opened')])
        data = [{"id": s.id, "name": s.config_id.name, "config_id": s.config_id.id, 
                 "auto_assign": s.config_id.auto_assign_waiting_guest, 
                 "waiting_duration": s.config_id.waiting_duration or 5} for s in sessions]
        return {"opened_sessions": data, "default_session_id": sessions[0].id if len(sessions) == 1 else None}