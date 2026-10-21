from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PosKitchenStation(models.Model):
    _name = "pos.kitchen.station"
    _description = "Kitchen Station"
    _inherit = ["pos.load.mixin", "pos.kitchen.access.mixin"]
    _order = "sequence, id"

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
             "the first one (sequence) gets the orders and the other one can take the overflow.")
    chef_ids = fields.Many2many(
        "pos.kitchen.chef", "pos_kitchen_chef_pos_kitchen_station_rel", "pos_kitchen_station_id",
        "pos_kitchen_chef_id", string="Chefs", help="Employees working on this station.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Char()
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
    def _kitchen_avg_minutes(self, product_ids, days=14, min_samples=3):
        since = fields.Datetime.now() - timedelta(days=days)
        rows = self.env["pos.kitchen.performance"].sudo()._read_group(
            [("sent_at", ">=", since), ("ready_at", "!=", False), ("product_id", "in", list(product_ids))],
            ["product_id"], ["prep_seconds:avg", "__count"])
        return {product.id: secs / 60.0 for product, secs, count in rows if count >= min_samples and secs}

    @api.model
    def _kitchen_item_minutes(self, product, measured):
        return product.product_tmpl_id._kitchen_prep_minutes() or measured.get(product.id, 0.0)

    def _kitchen_workload_data(self):
       
        by_display = defaultdict(lambda: self.browse())
        for station in self:
            by_display[station.prep_display_id.id] |= station
        states = self.env["pos.prep.state"].search([
            ("stage_id.prep_display_id", "in", list(by_display)),
            ("stage_id.stage_type", "in", ["todo", "in_progress"]),
            ("todo", "=", True),
            ("prep_line_id.prep_order_id.pos_order_id.session_id.state", "in", ["opened", "closing_control"]),
        ])
        products = states.prep_line_id.product_id
        measured = self._kitchen_avg_minutes(products.ids) if products else {}
        queues = {station.id: {} for station in self}
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
            entry = queues[station.id].setdefault(ticket.pos_order_id.id, [ticket.create_date, ticket.id, 0.0, 0.0])
            entry[0] = min(entry[0], ticket.create_date)
            entry[2] += qty
            entry[3] += qty * self._kitchen_item_minutes(line.product_id, measured)
        result = {}
        for station in self:
            ordered = sorted(queues[station.id].items(), key=lambda kv: (kv[1][0], kv[1][1]))
            overflow, used = [], 0.0
            for order_id, entry in ordered:
                used += entry[3] if station.workload_metric == "time" else entry[2]
                if station.workload_limit and used > station.workload_limit:
                    overflow.append(order_id)
            result[station.id] = {
                "orders": [(oid, e[2], e[3]) for oid, e in ordered], "overflow": overflow}
        return result

    @staticmethod
    def _kitchen_load(station, queue):
        index = 2 if station.workload_metric == "time" else 1
        return sum(order[index] for order in queue["orders"])

    @api.model
    def get_station_workload(self, display_id=False):
       
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
                "id": station.id, "name": station.name, "code": station.code, "color": station.color,
                "display_id": station.prep_display_id.id,
                "pending_orders": len(queue["orders"]),
                "metric": station.workload_metric, "value": value, "limit": limit,
                "free": max(round(limit - value, 1), 0) if limit else None,
                "overloaded": bool(limit and value > limit),
                "overflow_orders": len(queue["overflow"]),
                "overflow_order_ids": queue["overflow"],
                "alternatives": alternatives.ids,
            })
        return result

    def move_overflow(self, target_station_id, reason=False, actor_chef_id=False):
       
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

    #  KDS loading
    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [("active", "=", True)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ["id", "name", "code", "sequence", "color", "default_target_minutes", "workload_limit",
                "workload_metric", "display_id_int"]

    #  PoS loading
    @api.model
    def _load_pos_data_domain(self, data, config):
        return [("active", "=", True), ("company_id", "=", config.company_id.id),
                "|", ("pos_config_ids", "=", False), ("pos_config_ids", "in", config.id)]

    @api.model
    def _load_pos_data_fields(self, config):
        return ["id", "name", "code", "sequence", "color", "display_id_int"]
