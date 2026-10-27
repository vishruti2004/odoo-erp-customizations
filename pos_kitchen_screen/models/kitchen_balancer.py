
from datetime import datetime, timedelta
from odoo import fields

EPOCH = datetime(1970, 1, 1)
MIXED_METRIC_TOLERANCE = 0.10

def _station_keys(pool, tolerance):
    metrics = {candidate["metric"] for candidate in pool}
    if len(metrics) > 1 and all(candidate["limit"] for candidate in pool):
        return (lambda candidate: candidate["station_load"] / candidate["limit"]), MIXED_METRIC_TOLERANCE
    return (lambda candidate: candidate["station_load"]), tolerance

def metrics_of(pool):
    return {candidate["metric"] for candidate in pool}

def rank_candidates(candidates, tolerance=0.0):
    pool = list(candidates)
    if not pool:
        return None
    pool = [candidate for candidate in pool if candidate["chef"]] or pool
    pool = [candidate for candidate in pool if not candidate["over_limit"]] or pool
    tolerance = max(tolerance or 0.0, 0.0)

    station_key, station_tolerance = _station_keys(pool, tolerance)
    with_chef = [candidate for candidate in pool if candidate["chef"]]
    if with_chef:
        
        mixed = len(metrics_of(with_chef)) > 1 and all(candidate["limit"] for candidate in with_chef)

        def finish(c):
            return c["chef_load"] / c["limit"] if mixed else c["chef_load"]

        best = min(finish(candidate) for candidate in with_chef)
        pool = [candidate for candidate in with_chef if finish(candidate) <= best + 1e-9]
    else:
        best_station = min(station_key(candidate) for candidate in pool)
        pool = [candidate for candidate in pool if station_key(candidate) <= best_station + station_tolerance + 1e-9]

    def fair_turn(c):
        return (
            c["chef_count"],
            c["chef_last"] or EPOCH,
            c["station_last"] or EPOCH,
            c["chef_load"],
            station_key(c),
            c["chef_id"],
            c["station_id"],
        )

    return min(pool, key=fair_turn)


class KitchenBalancer:
    ASSIGN_TYPES = ("assign", "reassign", "auto_assign")
    def __init__(self, env, config, exclude_lines=None):
        self.env = env
        self.config = config
        self.tolerance = config.kitchen_balance_tolerance or 0.0
        self.Station = env["pos.kitchen.station"].sudo()
        self.now = fields.Datetime.now()
        session = config.current_session_id
        self.window_start = (session.start_at if session and session.start_at else self.now - timedelta(hours=12))
        self.station_load = {}
        self.chef_load = {}
        self.on_shift = None
        self.exclude_line_ids = set(exclude_lines.ids) if exclude_lines else set()

    def _ensure_stations(self, stations):
        missing = stations.filtered(lambda station: station.id not in self.station_load)
        if not missing:
            return
        pending = missing._kitchen_pending()
        turns = {
            station.id: (count, last) for station, count, last in self.env["pos.prep.line"].sudo()._read_group(
                [("station_id", "in", missing.ids), ("create_date", ">=", self.window_start)],
                ["station_id"], ["__count", "create_date:max"])
        }
        for station in missing:
            entries = [entry for entry in pending.get(station.id, []) if entry["line"].id not in self.exclude_line_ids]
            count, last = turns.get(station.id, (0, None))
            self.station_load[station.id] = {
                "minutes": sum(entry["minutes"] for entry in entries), "items": sum(entry["qty"] for entry in entries),
                "count": count, "last": last,
            }

    def _ensure_chefs(self, chefs):
        missing = chefs.filtered(lambda chef: chef.id not in self.chef_load)
        if not missing:
            return
        load = missing._kitchen_pending_load()
        turns = {
            chef.id: (count, last) for chef, count, last in self.env["pos.kitchen.assignment.history"].sudo()._read_group(
                [("new_chef_id", "in", missing.ids), ("move_type", "in", self.ASSIGN_TYPES),
                 ("changed_at", ">=", self.window_start)],
                ["new_chef_id"], ["__count", "changed_at:max"])
        }
        for chef in missing:
            count, last = turns.get(chef.id, (0, None))
            self.chef_load[chef.id] = dict(load[chef.id], count=count, last=last)

    def _ensure_on_shift(self, chefs):
        if self.on_shift is None:
            self.on_shift = set()
            self._shift_checked = set()
        todo = chefs.filtered(lambda chef: chef.id not in self._shift_checked)
        if todo:
            self.on_shift |= todo._kitchen_on_shift()
            self._shift_checked |= set(todo.ids)

    def eligible_chefs(self, station, product):
        chefs = station.sudo().chef_ids.filtered(
            lambda chef: chef.active and chef.company_id == self.config.company_id and chef._kitchen_can_cook(product))
        self._ensure_on_shift(chefs)
        return chefs.filtered(lambda chef: chef.id in self.on_shift)

    def _candidates(self, product, qty, stations):
        self._ensure_stations(stations)
        result = []
        for station in stations:
            minutes = qty * self.Station._kitchen_item_minutes(product, station)
            load = self.station_load[station.id]
            projected_minutes = load["minutes"] + minutes
            projected_items = load["items"] + qty
            metric = station.workload_metric
            projected = projected_minutes if metric == "time" else projected_items
            over = bool(station.workload_limit and projected > station.workload_limit)
            chefs = self.eligible_chefs(station, product)
            self._ensure_chefs(chefs)
            base = {
                "station": station, "station_id": station.id, "item_minutes": minutes, "qty": qty,
                "metric": metric, "limit": station.workload_limit, "station_load": projected,
                "item_load": minutes if metric == "time" else qty,
                "station_last": load["last"], "over_limit": over,
            }
            if not chefs:
                result.append(dict(base, chef=None, chef_id=0, chef_load=0.0, chef_count=0, chef_last=None))
            for chef in chefs:
                c_load = self.chef_load[chef.id]
                chef_projected = (c_load["minutes"] + minutes) if metric == "time" else (c_load["items"] + qty)
                result.append(dict(
                    base, chef=chef, chef_id=chef.id, chef_load=chef_projected,
                    chef_count=c_load["count"], chef_last=c_load["last"]))
        return result

    def pick(self, product, qty, stations):
        best = rank_candidates(self._candidates(product, qty, stations), self.tolerance)
        if not best:
            return self.Station.browse(), None, 0.0
        return best["station"], best["chef"], best["item_minutes"]

    def commit(self, station, chef, minutes, qty, station_load=True):
        if station and station_load:
            self._ensure_stations(station)
            load = self.station_load[station.id]
            load["minutes"] += minutes
            load["items"] += qty
            load["count"] += 1
            load["last"] = self.now
        if chef:
            self._ensure_chefs(chef)
            load = self.chef_load[chef.id]
            load["minutes"] += minutes
            load["items"] += qty
            load["count"] += 1
            load["last"] = self.now

    def release(self, station, chef, minutes, qty):
        if station:
            self._ensure_stations(station)
            load = self.station_load[station.id]
            load["minutes"] = max(load["minutes"] - minutes, 0.0)
            load["items"] = max(load["items"] - qty, 0.0)
        if chef:
            self._ensure_chefs(chef)
            load = self.chef_load[chef.id]
            load["minutes"] = max(load["minutes"] - minutes, 0.0)
            load["items"] = max(load["items"] - qty, 0.0)
