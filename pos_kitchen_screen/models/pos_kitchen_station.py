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
        help="Every product of these categories is prepared here. When two stations share a category, "
             "the first one created gets the orders and the other one can take the overflow.")
    chef_ids = fields.Many2many(
        "pos.kitchen.chef", "pos_kitchen_chef_pos_kitchen_station_rel", "pos_kitchen_station_id",
        "pos_kitchen_chef_id", string="Chefs", help="Employees working on this station.")
    active = fields.Boolean(default=True)
    default_target_minutes = fields.Float(
        "Default target (min)", help="Target used by the delay report when the product and its category have none.")
    workload_metric = fields.Selection(
        [("time", "Time wise"), ("items", "Item wise")], default="items", required=True,
        help="Time wise: the preparation minutes of the pending items are added up.\n"
             "Item wise: the pending items are counted.")
    workload_limit = fields.Float(
        "Workload limit", help="Maximum the station can handle at once (minutes or items, see metric). "
                               "Orders beyond it, in arrival order, are flagged as overflow. 0 = no limit.")
    display_id_int = fields.Integer(compute="_compute_display_id_int")

    _code_company_uniq = models.Constraint(
        "UNIQUE(code, company_id)", "The station code must be unique per company.")

    @api.depends("prep_display_id")
    def _compute_display_id_int(self):
        for station in self:
            station.display_id_int = station.prep_display_id.id

    # ------------------------------------------------------------------ constraints
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

    # ------------------------------------------------------------------ routing
    @api.model
    def _kitchen_find_station(self, config, product, override=None):
        if override and override.exists() and override.active and override.company_id == config.company_id:
            return override
        stations = self.sudo().search([
            ("active", "=", True), ("company_id", "=", config.company_id.id),
            "|", ("pos_config_ids", "=", False), ("pos_config_ids", "in", config.id),
        ])
        categories = product.pos_categ_ids
        for station in stations:
            if station.category_ids & categories:
                return station
        return self.browse()

    def _kitchen_handles(self, product):
        self.ensure_one()
        return bool(self.category_ids & product.pos_categ_ids)

    #  workload
    @api.model
    def _kitchen_item_minutes(self, product, station):
        """Minutes to prepare one unit: product, else its PoS category, else the station default target."""
        return product.product_tmpl_id._kitchen_prep_minutes() or station.default_target_minutes

    def _kitchen_pending(self):
        """Pending work of the stations on open sessions, one entry per prep line.

        {station_id: [{"line", "state", "order_id", "ticket_date", "ticket_id", "qty", "minutes"}]}
        minutes = quantity x preparation time (the workload, not the elapsed time). Cancelled quantity is excluded.
        """
        by_display = defaultdict(lambda: self.browse())
        for station in self:
            by_display[station.prep_display_id.id] |= station
        states = self.env["pos.prep.state"].search([
            ("stage_id.prep_display_id", "in", list(by_display)),
            ("stage_id.stage_type", "in", ["todo", "in_progress"]),
            ("todo", "=", True),
            ("prep_line_id.prep_order_id.pos_order_id.session_id.state", "in", ["opened", "closing_control"]),
        ])
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
        """Queue per station in arrival order (oldest ticket first).

        {station_id: {"orders": [(pos_order_id, items, minutes)], "overflow": [pos_order_id]}}
        An order is overflow once the cumulative load (items, or minutes) goes beyond the station limit.
        """
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
            overflow, used = [], 0.0
            for order_id, row in ordered:
                used += row[3] if station.workload_metric == "time" else row[2]
                if station.workload_limit and used > station.workload_limit:
                    overflow.append(order_id)
            result[station.id] = {"orders": [(oid, r[2], r[3]) for oid, r in ordered], "overflow": overflow}
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
                "excess": max(round(value - limit, 1), 0) if limit else 0,
                "overloaded": bool(limit and value > limit),
                "overflow_orders": len(queue["overflow"]),
                "overflow_order_ids": queue["overflow"],
                "alternatives": alternatives.ids,
            })
        return result

    # -- item wise: move the orders queued beyond the limit
    def move_overflow(self, target_station_id, reason=False, actor_chef_id=False):
        """RPC (called with [[station_id], target_station_id, reason, actor_chef_id]). Item wise stations."""
        self.ensure_one()
        target = self.browse(int(target_station_id)).exists()
        if not target or target == self:
            raise UserError(_("Choose another station."))
        data = (self | target)._kitchen_workload_data()
        overflow = data[self.id]["overflow"]
        if not overflow:
            return {"moved": [], "skipped": [], "remaining": 0}
        weights = {oid: (items, minutes) for oid, items, minutes in data[self.id]["orders"]}
        index = 1 if target.workload_metric == "time" else 0
        free = None
        if target.workload_limit:
            free = target.workload_limit - self._kitchen_load(target, data[target.id])
        chosen, acc = [], 0.0
        for order_id in overflow:
            weight = weights[order_id][index]
            if free is not None and acc + weight > free:
                break
            chosen.append(order_id)
            acc += weight
        if not chosen:
            raise UserError(_("Station %s has no free capacity.", target.name))
        states = self.env["pos.prep.state"].search([
            ("stage_id.prep_display_id", "=", self.prep_display_id.id),
            ("prep_line_id.prep_order_id.pos_order_id", "in", chosen),
        ])
        lines = states.prep_line_id.filtered(lambda l: not l.pos_order_line_id.combo_line_ids)
        result = lines.reassign(target.id, reason, actor_chef_id)
        result["remaining"] = len(overflow) - len(chosen)
        return result

    # -- time wise: move the order lines that remove the excess minutes
    @staticmethod
    def _kitchen_pick_subset(items, excess, capacity):
        """Choose items [(key, minutes)] whose total covers `excess` with the least overshoot.

        An exact match is preferred. When the excess cannot be covered, the largest total that fits
        in `capacity` (None = unlimited) is returned. Whole lines only: quantities are not split.
        """
        scale = 10
        weights = [(key, int(round(minutes * scale))) for key, minutes in items if minutes > 0]
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

    def _kitchen_compatible_stations(self):
        """Other time wise stations of the same company / PoS that prepare one of this station's categories."""
        self.ensure_one()
        others = self.search([
            ("id", "!=", self.id), ("active", "=", True), ("company_id", "=", self.company_id.id),
            ("workload_metric", "=", "time"),
        ])
        return others.filtered(
            lambda o: o.category_ids & self.category_ids
            and (not o.pos_config_ids or not self.pos_config_ids or o.pos_config_ids & self.pos_config_ids))

    @staticmethod
    def _kitchen_movable(entry):
        """Only items nobody started: first stage, not crossed off, no chef, not a combo parent."""
        line, state = entry["line"], entry["state"]
        return (state.stage_id.stage_type == "todo" and state.todo and not line.assigned_chef_id
                and not line.pos_order_line_id.combo_line_ids and entry["minutes"] > 0)

    def plan_overload(self):
        """RPC (called with [[station_id]]): preview which order lines would be moved, and where."""
        self.ensure_one()
        plan = {"station": self.name, "excess": 0.0, "destination": False, "lines": [],
                "moved_minutes": 0.0, "exact": False, "reason": False}
        if self.workload_metric != "time" or not self.workload_limit:
            plan["reason"] = _("Time wise workload with a limit is not configured on this station.")
            return plan
        candidates = self._kitchen_compatible_stations()
        pending = (self | candidates)._kitchen_pending()
        load = sum(e["minutes"] for e in pending[self.id])
        excess = round(max(load - self.workload_limit, 0.0), 1)
        plan["excess"] = excess
        if not excess:
            plan["reason"] = _("The station is within its capacity.")
            return plan
        movable = [e for e in pending[self.id] if self._kitchen_movable(e)]
        if not movable:
            plan["reason"] = _("No pending item can be moved: they are already started or assigned.")
            return plan
        best = None
        for dest in candidates:
            free = None
            if dest.workload_limit:
                free = dest.workload_limit - sum(e["minutes"] for e in pending[dest.id])
                if free <= 0:
                    continue
            usable = [e for e in movable if dest._kitchen_handles(e["line"].product_id)]
            capacity = free
            for _attempt in range(20):
                keys, moved = self._kitchen_pick_subset(
                    [(e["line"].id, e["minutes"]) for e in usable], excess, capacity)
                chosen = [e for e in usable if e["line"].id in keys]
                # the destination counts the same items with its own preparation times
                dest_minutes = sum(e["qty"] * self._kitchen_item_minutes(e["line"].product_id, dest) for e in chosen)
                if free is None or dest_minutes <= free or not chosen:
                    break
                capacity = (capacity if capacity is not None else moved) - 0.5
            if not chosen:
                continue
            score = (abs(moved - excess) < 0.05, moved >= excess, -abs(moved - excess), free if free is not None else 1e9)
            if best is None or score > best[0]:
                best = (score, dest, chosen, moved, free)
        if not best:
            plan["reason"] = _("No compatible station has free capacity.")
            _logger.warning("Kitchen overload on %s (+%s min): %s", self.name, excess, plan["reason"])
            self.prep_display_id._notify("OVERLOAD_UNRESOLVED", {"station": self.name, "excess": excess})
            return plan
        _score, dest, chosen, moved, free = best
        plan.update({
            "destination": {"id": dest.id, "name": dest.name, "free": None if free is None else round(free, 1)},
            "lines": [{
                "line_id": e["line"].id, "product": e["line"].product_id.display_name, "qty": e["qty"],
                "minutes": round(e["minutes"], 1), "order": e["line"].prep_order_id.order_name,
            } for e in chosen],
            "moved_minutes": round(moved, 1), "exact": abs(moved - excess) < 0.05,
        })
        return plan

    def resolve_overload(self, destination_id, line_ids, reason=False, actor_chef_id=False):
        """RPC (called with [[station_id], destination_id, line_ids, reason, actor_chef_id]).

        Revalidates everything, locks the rows against concurrent moves and reassigns only the chosen
        order lines. The order, product, quantity and order status are untouched.
        """
        self.ensure_one()
        dest = self.browse(int(destination_id)).exists()
        if self.workload_metric != "time" or not dest or dest not in self._kitchen_compatible_stations():
            raise UserError(_("This station cannot take the work of %s.", self.name))
        lines = self.env["pos.prep.line"].browse(line_ids).exists()
        if not lines:
            raise UserError(_("Nothing to move."))
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM pos_prep_state WHERE prep_line_id IN %s FOR UPDATE NOWAIT", (tuple(lines.ids),))
        except psycopg2.errors.LockNotAvailable:
            raise UserError(_("These items are being changed by someone else. Try again."))
        lines.invalidate_recordset()
        pending = (self | dest)._kitchen_pending()
        by_line = {e["line"].id: e for e in pending[self.id]}
        if any(line.id not in by_line or not self._kitchen_movable(by_line[line.id]) for line in lines):
            raise UserError(_("Some items changed in the meantime. Check the proposal again."))
        if any(not dest._kitchen_handles(line.product_id) for line in lines):
            raise UserError(_("%s does not prepare these products.", dest.name))
        if dest.workload_limit:
            free = dest.workload_limit - sum(e["minutes"] for e in pending[dest.id])
            needed = sum(
                (line.quantity - line.cancelled) * self._kitchen_item_minutes(line.product_id, dest) for line in lines)
            if needed > free + 0.05:
                raise UserError(_("%s has no more room for these items.", dest.name))
        result = lines.reassign(dest.id, reason, actor_chef_id)
        _logger.info("Kitchen overload: %s line(s) moved from %s to %s", len(result["moved"]), self.name, dest.name)
        return result

    #  KDS loading
    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [("active", "=", True)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ["id", "name", "code","default_target_minutes", "workload_limit",
                "workload_metric", "display_id_int"]

    #  PoS loading
    @api.model
    def _load_pos_data_domain(self, data, config):
        return [("active", "=", True), ("company_id", "=", config.company_id.id),
                "|", ("pos_config_ids", "=", False), ("pos_config_ids", "in", config.id)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["id", "name", "code", "display_id_int"]
