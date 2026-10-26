import logging
from collections import defaultdict

import psycopg2.errors

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class PosKitchenStation(models.Model):
    _name = "pos.kitchen.station"
    _description = "Kitchen Station"
    _inherit = ["pos.load.mixin", "pos.kitchen.access.mixin"]
    _order = "id"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    pos_config_ids = fields.Many2many("pos.config", string="Point of Sale",
                                      help="Where the station applies. Empty = all.")
    prep_display_id = fields.Many2one("pos.prep.display", string="Preparation Display", required=True,
                                      ondelete="restrict", index=True,
                                      help="The screen that shows this station.")
    category_ids = fields.Many2many(
        "pos.category", string="Categories",
        help="Every product of these categories is prepared here. When two stations share a category, Dynamic "
             "Automatic Assignment sends each item to the station with the lowest projected workload (Item Wise or "
             "Time Wise, as set on each station). Manual Assignment: the first one created gets the orders and the "
             "other one can take the overflow.")
    chef_ids = fields.Many2many(
        "pos.kitchen.chef", "pos_kitchen_chef_pos_kitchen_station_rel", "pos_kitchen_station_id",
        "pos_kitchen_chef_id", string="Chefs", help="Employees working on this station.")
    active = fields.Boolean(default=True)
    default_target_minutes = fields.Float(
        "Default target (min)", help="Time Wise stations: preparation time used for the workload and the delay "
                                     "report when the product and its category have none.")
    workload_metric = fields.Selection(
        [("time", "Time wise"), ("items", "Item wise")], default="items", required=True,
        help="Time wise: the preparation minutes of the pending items are added up.\n"
             "Item wise: the pending items are counted.")
    workload_limit = fields.Float(
        "Workload limit", help="Maximum the station can handle at once (minutes or items, see metric). "
                               "Orders beyond it, in arrival order, are flagged as overflow. 0 = no limit.")
    display_id_int = fields.Integer(compute="_compute_display_id_int")
    category_ids_int = fields.Json(compute="_compute_category_ids_int")
    kanban_category_names = fields.Json(compute="_compute_kanban_names")
    kanban_chef_names = fields.Json(compute="_compute_kanban_names")

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "The station code must be unique per company.")

    @api.depends("prep_display_id")
    def _compute_display_id_int(self):
        for station in self:
            station.display_id_int = station.prep_display_id.id

    @api.depends("category_ids")
    def _compute_category_ids_int(self):
        for station in self:
            station.category_ids_int = station.category_ids.ids

    @api.depends("category_ids.name", "chef_ids.name")
    def _compute_kanban_names(self):
        for station in self:
            station.kanban_category_names = station.category_ids.mapped("display_name")
            station.kanban_chef_names = [name for name in station.chef_ids.mapped("name") if name]

    @api.model
    def web_search_read(self, domain, specification, **kwargs):
        """Backend views: a chef sees only his own stations."""
        if not self._kitchen_is_manager():
            domain = list(domain or []) + [("id", "in", self._kitchen_user_chef().station_ids.ids)]
        return super().web_search_read(domain, specification, **kwargs)

    @api.onchange("prep_display_id")
    def _onchange_prep_display_id(self):
        """The station takes the Points of Sale and the categories of its preparation display."""
        display = self.prep_display_id
        if not display:
            return
        if display.company_id:
            self.company_id = display.company_id
        if "pos_config_ids" in display._fields:
            self.pos_config_ids = display.pos_config_ids
        if "category_ids" in display._fields and display.category_ids:
            self.category_ids = display.category_ids

    @api.constrains("company_id", "prep_display_id", "pos_config_ids", "category_ids", "chef_ids")
    def _check_company(self):
        for station in self:
            if station.prep_display_id.company_id != station.company_id:
                raise ValidationError(_("Station %s and its preparation display must belong to the same company.", station.name))
            if station.pos_config_ids.company_id - station.company_id:
                raise ValidationError(_("Station %s is linked to a Point of Sale of another company.", station.name))
            if station.chef_ids.company_id - station.company_id:
                raise ValidationError(_("The chefs of station %s must belong to the same company.", station.name))

    @api.constrains("pos_config_ids", "prep_display_id")
    def _check_display_covers_configs(self):
        for station in self:
            display = station.prep_display_id
            if not display.pos_config_ids:
                continue
            if not station.pos_config_ids or (station.pos_config_ids - display.pos_config_ids):
                raise ValidationError(_(
                    "The Point of Sale of station %(station)s must be covered by its preparation display %(display)s.",
                    station=station.name, display=display.name))

    #  routing
    @api.model
    def _kitchen_find_station(self, config, product, override=None, qty=1.0, balancer=None):
        """Station of a new item: the manual override, else the balanced choice (several stations handle the
        category and a balancer is given), else the first station of the category."""
        if override and override.exists() and override.active and override.company_id == config.company_id:
            return override
        stations = self.sudo().search([
            ("active", "=", True), ("company_id", "=", config.company_id.id),
            "|", ("pos_config_ids", "=", False), ("pos_config_ids", "in", config.id),
        ])
        categories = product.pos_categ_ids
        matching = stations.filtered(lambda s: s.category_ids & categories)
        if balancer is not None and len(matching) > 1:
            station, chef, minutes = balancer.pick(product, qty, matching)
            if station:
                balancer.commit(station, chef, minutes, qty)
                return station
        return matching[:1]

    @api.model
    def _kitchen_plan_stations(self, config, product, qty, balancer):
        """[(station, units)] for a new item of ``qty`` units in Dynamic Automatic mode: every unit goes, one by
        one, to the category-compatible station that finishes it first (the snapshot is updated after each
        unit), so the quantity is spread equally over the stations. A single station / decimal quantity
        keeps the whole item together."""
        stations = self.sudo().search([
            ("active", "=", True), ("company_id", "=", config.company_id.id),
            "|", ("pos_config_ids", "=", False), ("pos_config_ids", "in", config.id),
        ]).filtered(lambda s: s.category_ids & product.pos_categ_ids)
        if len(stations) < 2 or qty < 2 or not float(qty).is_integer():
            return []
        plan = {}
        for _unit in range(int(qty)):
            station, chef, minutes = balancer.pick(product, 1.0, stations)
            if not station:
                break
            balancer.commit(station, chef, minutes, 1.0)
            plan[station] = plan.get(station, 0) + 1
        return list(plan.items()) if len(plan) > 1 and sum(plan.values()) == qty else []

    def _kitchen_handles(self, product):
        self.ensure_one()
        return bool(self.category_ids & product.pos_categ_ids)

    #  workload
    @api.model
    def _kitchen_item_minutes(self, product, station):
        # the station default only applies to Time Wise stations (it is hidden on Item Wise ones)
        default = station.default_target_minutes if station and station.workload_metric == "time" else 0.0
        return product.product_tmpl_id._kitchen_prep_minutes() or default

    @api.model
    def _kitchen_pending_state_domain(self):
        """States still to prepare (to do / in progress, not crossed off) on open sessions.
        Ready, done, cancelled items leave it; re-prepared items come back: the workload follows."""
        return [
            ("stage_id.stage_type", "in", ["todo", "in_progress"]),
            ("todo", "=", True),
            ("prep_line_id.prep_order_id.pos_order_id.session_id.state", "in", ["opened", "closing_control"]),
        ]

    def _kitchen_pending(self):
        by_display = defaultdict(lambda: self.browse())
        for station in self:
            by_display[station.prep_display_id.id] |= station
        states = self.env["pos.prep.state"].search([
            ("stage_id.prep_display_id", "in", list(by_display)),
        ] + self._kitchen_pending_state_domain())
        pending = {station.id: [] for station in self}
        for state in states:
            line = state.prep_line_id
            qty = line.quantity - line.cancelled
            if qty <= 0:
                continue
            display_stations = by_display.get(state.stage_id.prep_display_id.id)
            station = line.station_id if line.station_id in self else (display_stations[:1] if display_stations else None)
            if not station:
                continue
            ticket = line.prep_order_id
            pending[station.id].append({
                "line": line, "state": state, "order_id": ticket.pos_order_id.id,
                "ticket_date": ticket.create_date, "ticket_id": ticket.id, "qty": qty,
                "minutes": qty * self._kitchen_item_minutes(line.product_id, station),
            })
        return pending

    def _kitchen_workload_data(self):
        pending = self._kitchen_pending()
        result = {}
        for station in self:
            queue = {}
            for entry in pending[station.id]:
                row = queue.setdefault(entry["order_id"], [entry["ticket_date"], entry["ticket_id"], 0.0, 0.0])
                row[0] = min(row[0], entry["ticket_date"])
                row[2] += entry["qty"]
                row[3] += entry["minutes"]
            ordered = sorted(queue.items(), key=lambda kv: (kv[1][0], kv[1][1]))
            # the overload flow starts once a chef took an order at the station
            active = any(entry["line"].assigned_chef_id for entry in pending[station.id])
            overflow, used = [], 0.0
            for order_id, row in ordered:
                used += row[3] if station.workload_metric == "time" else row[2]
                if active and station.workload_limit and used > station.workload_limit:
                    overflow.append(order_id)
            result[station.id] = {
                "orders": [(oid, r[2], r[3]) for oid, r in ordered], "overflow": overflow, "active": active}
        return result

    @staticmethod
    def _kitchen_load(station, queue):
        index = 2 if station.workload_metric == "time" else 1
        return sum(order[index] for order in queue["orders"])

    @api.model
    def get_station_workload(self, display_id=False):
        """RPC: workload per station on open sessions (computed on demand, never stored)."""
        domain = [("active", "=", True)]
        if display_id:
            configs = self.env["pos.prep.display"].browse(int(display_id))._get_pos_config_ids()
            domain += ["|", ("pos_config_ids", "=", False), ("pos_config_ids", "in", configs.ids)]
        stations = self.search(domain)
        data = stations._kitchen_workload_data() if stations else {}
        result = []
        for station in stations:
            queue = data[station.id]
            value = round(self._kitchen_load(station, queue), 1)
            limit = station.workload_limit
            alternatives = stations.filtered(
                lambda o: o != station and o.category_ids & station.category_ids
                and (not o.pos_config_ids or not station.pos_config_ids or o.pos_config_ids & station.pos_config_ids))
            result.append({
                "id": station.id, "name": station.name, "code": station.code,
                "display_id": station.prep_display_id.id,
                "pending_orders": len(queue["orders"]),
                "metric": station.workload_metric, "value": value, "limit": limit,
                "ratio": round(value / limit * 100) if limit else 0,
                "free": max(round(limit - value, 1), 0) if limit else None,
                "excess": max(round(value - limit, 1), 0) if limit and queue["active"] else 0,
                "overloaded": bool(limit and queue["active"] and value > limit),
                "active": queue["active"],
                "overflow_orders": len(queue["overflow"]),
                "overflow_order_ids": queue["overflow"],
                "alternatives": alternatives.ids,
            })
        return result

    # -- overload: move whole order lines (never whole orders) to another station
    @staticmethod
    def _kitchen_pick_subset(items, excess, capacity):
        scale = 10
        weights = [(key, int(round(weight * scale))) for key, weight in items if weight > 0]
        total = sum(weight for _key, weight in weights)
        limit = total if capacity is None else min(int(capacity * scale), total)
        reachable = {0: ()}
        for key, weight in weights:
            for subtotal, chosen in list(reachable.items()):
                new = subtotal + weight
                if new <= limit and new not in reachable:
                    reachable[new] = chosen + (key,)
        target = int(round(excess * scale))
        covering = [t for t in reachable if t >= max(target, 1)]
        best = min(covering) if covering else max(reachable)
        return list(reachable[best]), best / scale

    def _kitchen_weight(self, entry):
        """Load of a pending line for this station: preparation minutes (time wise) or items (item wise)."""
        self.ensure_one()
        return entry["minutes"] if self.workload_metric == "time" else entry["qty"]

    def _kitchen_load_of(self, entries):
        return sum(self._kitchen_weight(e) for e in entries)

    def _kitchen_compatible_stations(self):
        self.ensure_one()
        others = self.search([
            ("id", "!=", self.id), ("active", "=", True), ("company_id", "=", self.company_id.id),
            ("workload_metric", "=", self.workload_metric),
        ])
        return others.filtered(
            lambda o: o.category_ids & self.category_ids
            and (not o.pos_config_ids or not self.pos_config_ids or o.pos_config_ids & self.pos_config_ids))

    @staticmethod
    def _kitchen_movable(entry):
        line, state = entry["line"], entry["state"]
        return (state.stage_id.stage_type == "todo" and state.todo and line._kitchen_chef_movable()
                and not line.pos_order_line_id.combo_line_ids)

    def plan_overload(self, notify=True):
        self.ensure_one()
        unit = "min" if self.workload_metric == "time" else "items"
        plan = {"station": self.name, "unit": unit, "excess": 0.0, "destination": False, "lines": [],
                "moved": 0.0, "exact": False, "reason": False}
        if not self.workload_limit:
            plan["reason"] = _("No workload limit is set.")
            return plan
        candidates = self._kitchen_compatible_stations()
        pending = (self | candidates)._kitchen_pending()
        if not any(e["line"].assigned_chef_id for e in pending[self.id]):
            plan["reason"] = _("No active chef at this station.")
            return plan
        excess = round(max(self._kitchen_load_of(pending[self.id]) - self.workload_limit, 0.0), 1)
        plan["excess"] = excess
        if not excess:
            plan["reason"] = _("Station is within capacity.")
            return plan
        movable = [e for e in pending[self.id] if self._kitchen_movable(e)]
        if not movable:
            plan["reason"] = _("Pending items are already started or manually assigned.")
            return plan
        best = None
        for dest in candidates:
            free = None
            if dest.workload_limit:
                free = dest.workload_limit - dest._kitchen_load_of(pending[dest.id])
                if free <= 0:
                    continue
            usable = [e for e in movable if dest._kitchen_handles(e["line"].product_id)]
            capacity = free
            for _attempt in range(20):
                keys, moved = self._kitchen_pick_subset(
                    [(e["line"].id, self._kitchen_weight(e)) for e in usable], excess, capacity)
                chosen = [e for e in usable if e["line"].id in keys]
                # the destination counts the same items with its own preparation times
                dest_load = sum(dest._kitchen_weight(dict(e, minutes=e["qty"] * self._kitchen_item_minutes(
                    e["line"].product_id, dest))) for e in chosen)
                if free is None or dest_load <= free or not chosen:
                    break
                capacity = (capacity if capacity is not None else moved) - 0.5
            if not chosen:
                continue
            score = (abs(moved - excess) < 0.05, moved >= excess, -abs(moved - excess),
                     free if free is not None else 1e9)
            if best is None or score > best[0]:
                best = (score, dest, chosen, moved, free)
        if not best:
            plan["reason"] = _("No compatible station has free capacity.")
            if notify:
                _logger.warning("Kitchen overload on %s (+%s %s): %s", self.name, excess, unit, plan["reason"])
                self.prep_display_id._notify(
                    "OVERLOAD_UNRESOLVED", {"id": self.id, "station": self.name, "excess": excess, "unit": unit})
            return plan
        _score, dest, chosen, moved, free = best
        plan.update({
            "destination": {"id": dest.id, "name": dest.name, "free": None if free is None else round(free, 1)},
            "lines": [{
                "line_id": e["line"].id, "product": e["line"].product_id.display_name, "qty": e["qty"],
                "load": round(self._kitchen_weight(e), 1), "order": e["line"].prep_order_id.order_name,
            } for e in chosen],
            "moved": round(moved, 1), "exact": abs(moved - excess) < 0.05,
        })
        return plan

    def resolve_overload(self, destination_id, line_ids, reason=False, actor_chef_id=False):
        self.ensure_one()
        if not self.env.context.get("kitchen_auto_move"):
            self._kitchen_check_manager(_("Only kitchen managers can move items."))
        dest = self.browse(int(destination_id)).exists()
        if not dest or dest not in self._kitchen_compatible_stations():
            raise UserError(_("%s cannot take these items.", self.name))
        lines = self.env["pos.prep.line"].browse(line_ids).exists()
        if not lines:
            raise UserError(_("Nothing to move."))
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM pos_prep_state WHERE prep_line_id IN %s FOR UPDATE NOWAIT", (tuple(lines.ids),))
        except psycopg2.errors.LockNotAvailable:
            raise UserError(_("Items are being updated. Please try again."))
        lines.invalidate_recordset()
        pending = (self | dest)._kitchen_pending()
        by_line = {e["line"].id: e for e in pending[self.id]}
        if any(line.id not in by_line or not self._kitchen_movable(by_line[line.id]) for line in lines):
            raise UserError(_("Items have changed. Please review the move again."))
        if any(not dest._kitchen_handles(line.product_id) for line in lines):
            raise UserError(_("%s does not handle this category.", dest.name))
        if dest.workload_limit:
            free = dest.workload_limit - dest._kitchen_load_of(pending[dest.id])
            needed = sum(
                dest._kitchen_weight({
                    "qty": line.quantity - line.cancelled,
                    "minutes": (line.quantity - line.cancelled) * self._kitchen_item_minutes(line.product_id, dest)})
                for line in lines)
            if needed > free + 0.05:
                raise UserError(_("%s has no free capacity.", dest.name))
        result = lines.reassign(dest.id, reason, actor_chef_id)
        _logger.info("Kitchen overload: %s line(s) moved from %s to %s", len(result["moved"]), self.name, dest.name)
        return result

    # -- Dynamic Automatic Assignment: the overflow moves by itself
    def _kitchen_auto_mode(self):
        """Dynamic Automatic Assignment is active on a Point of Sale of this station."""
        self.ensure_one()
        configs = self.pos_config_ids or self.env["pos.config"].sudo().search(
            [("company_id", "=", self.company_id.id)])
        return any(config._kitchen_auto() for config in configs)

    def _kitchen_auto_resolve_overload(self, notify_unresolved=False):
        """Move the excess of the overloaded stations (Dynamic Automatic mode) to compatible stations with
        free capacity, exactly like the "move items" button, without asking. Only items that are not started
        and have no manually chosen chef move; the destination gives them a chef. When no station can take
        the work the usual "over capacity" alert is shown (``notify_unresolved``)."""
        moved = []
        stations = self.filtered(lambda s: s.active and s.workload_limit)
        data = stations._kitchen_workload_data() if stations else {}
        overloaded = stations.filtered(
            lambda s: data[s.id]["active"] and self._kitchen_load(s, data[s.id]) > s.workload_limit)
        for station in overloaded.filtered(lambda s: s._kitchen_auto_mode()):
            for _attempt in range(5):  # one destination per pass, several if one is not enough
                plan = station.plan_overload(notify=notify_unresolved)
                if not plan["destination"] or not plan["lines"]:
                    break
                try:
                    with self.env.cr.savepoint():
                        result = station.with_context(kitchen_auto_move=True).resolve_overload(
                            plan["destination"]["id"], [l["line_id"] for l in plan["lines"]],
                            _("Auto overflow: %(station)s +%(excess)s %(unit)s",
                              station=station.name, excess=plan["excess"], unit=plan["unit"]))
                except UserError as error:
                    _logger.info("Kitchen automatic overflow on %s skipped: %s", station.name, error)
                    break
                if not result["moved"]:
                    break
                moved += result["moved"]
                notify_unresolved = False  # the alert, if any, is for the rest of the excess
        return moved

    @api.model
    def _kitchen_auto_resolve_overload_for(self, company):
        stations = self.sudo().search([
            ("active", "=", True), ("company_id", "=", company.id), ("workload_limit", ">", 0)])
        return stations._kitchen_auto_resolve_overload()

    #  KDS loading
    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [("active", "=", True)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ["id", "name", "code", "default_target_minutes", "workload_limit",
                "workload_metric", "display_id_int", "category_ids_int"]

    #  PoS loading
    @api.model
    def _load_pos_data_domain(self, data, config):
        return [("active", "=", True), ("company_id", "=", config.company_id.id),
                "|", ("pos_config_ids", "=", False), ("pos_config_ids", "in", config.id)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["id", "name", "code", "display_id_int"]