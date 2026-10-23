from datetime import timedelta

import pytz

from odoo import api, fields, models
from odoo.tools import SQL

HOURS = [(f"{hour:02d}", f"{hour:02d}:00 - {hour:02d}:59") for hour in range(24)]


class PosKitchenPerformance(models.Model):
  
    _name = "pos.kitchen.performance"
    _description = "Kitchen Performance Log"
    _order = "sent_at desc, id desc"

    company_id = fields.Many2one("res.company", string="Company", index=True)
    config_id = fields.Many2one("pos.config", string="Point of Sale", ondelete="set null", index=True)
    session_id = fields.Many2one("pos.session", string="Session", ondelete="set null", index=True)
    pos_order_id = fields.Many2one("pos.order", string="PoS Order", ondelete="set null")
    pos_order_line_id = fields.Many2one("pos.order.line", ondelete="set null")
    prep_line_id = fields.Many2one("pos.prep.line", ondelete="set null", index=True)
    station_id = fields.Many2one("pos.kitchen.station", string="Station", ondelete="set null")
    chef_id = fields.Many2one("pos.kitchen.chef", string="Chef", ondelete="set null")
    product_id = fields.Many2one("product.product", string="Product", ondelete="set null")
    order_name = fields.Char("Order")
    priority_at_send = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")], string="Priority", default="medium")

    qty = fields.Float("Quantity sent", digits=(16, 1))
    cancelled_qty = fields.Float("Cancelled quantity", digits=(16, 1))
    sent_at = fields.Datetime("Sent to kitchen", index=True)
    started_at = fields.Datetime("Started")
    ready_at = fields.Datetime("Ready")
    served_at = fields.Datetime("Served")
    target_seconds = fields.Float("Target (s)", help="Preparation time expected for the item, in seconds.")
    status = fields.Selection(
        [("waiting", "Waiting"), ("preparing", "Being prepared"), ("ready", "Ready"), ("served", "Served")],
        compute="_compute_figures", store=True)
    hour_of_day = fields.Selection(
        HOURS, string="Hour of the day", compute="_compute_hour_of_day", store=True,
        help="Hour at which the item was sent to the kitchen, in the time zone of the company "
             "(else of the user who sent it).")

    net_qty = fields.Float(
        "Items", compute="_compute_figures", store=True, digits=(16, 1), aggregator="sum",
        help="Quantity sent minus the quantity cancelled.")
    line_count = fields.Integer(
        "Order lines", compute="_compute_figures", store=True, aggregator="sum",
        help="Number of products (lines) sent to the kitchen.")
    is_measured = fields.Boolean(
        "Measured", compute="_compute_figures", store=True,
        help="Ready, not fully cancelled and with a target time: the lines used for every time figure.")
    untargeted_count = fields.Integer(
        "No target time", compute="_compute_figures", store=True, aggregator="sum",
        help="Ready lines without any target time (product, PoS category, station default). "
             "They are not measured: set a preparation time to include them.")

    prep_minutes = fields.Float(
        "Avg. preparation (min)", compute="_compute_figures", store=True, digits=(16, 1), aggregator="avg",
        help="Minutes between the item reaching the kitchen and the item being ready (measured lines).")
    target_minutes = fields.Float(
        "Avg. target (min)", compute="_compute_figures", store=True, digits=(16, 1), aggregator="avg",
        help="Time expected for the item: product, else PoS category, else station default (measured lines).")
    diff_minutes = fields.Float(
        "Avg. difference (min)", compute="_compute_figures", store=True, digits=(16, 1), aggregator="avg",
        help="Preparation minus target on the measured lines. Negative: faster than the target. "
             "Positive: slower.")
    late_lines = fields.Integer(
        "Late Items", compute="_compute_figures", store=True, aggregator="sum",
        help="Measured lines that took longer than their target time.")
    on_time_pct = fields.Float(
        "On time (%)", compute="_compute_figures", store=True, digits=(16, 0), aggregator="avg",
        help="Share of the measured lines that were ready within their target time.")
    late_minutes = fields.Float(
        "Avg. delay of late lines (min)", compute="_compute_figures", store=True, digits=(16, 1),
        aggregator="avg", help="Minutes beyond the target, averaged on the late lines only.")
    start_minutes = fields.Float(
        "Avg. time to start (min)", compute="_compute_figures", store=True, digits=(16, 1), aggregator="avg",
        help="Minutes between the item reaching the kitchen and the work starting (chef assigned or "
             "item crossed off), on the lines that started.")
    serve_minutes = fields.Float(
        "Avg. wait before serving (min)", compute="_compute_figures", store=True, digits=(16, 1),
        aggregator="avg", help="Minutes the item waited between Ready and Served, on the served lines.")
    is_late = fields.Boolean("Late", compute="_compute_figures", store=True)

    _station_sent_idx = models.Index("(station_id, sent_at)")

    #  computation
    @api.depends("sent_at", "company_id.partner_id.tz", "create_uid.tz")
    def _compute_hour_of_day(self):
        for rec in self:
            tz = pytz.timezone(rec.company_id.partner_id.tz or rec.create_uid.tz or "UTC")
            rec.hour_of_day = f"{pytz.utc.localize(rec.sent_at).astimezone(tz).hour:02d}" if rec.sent_at else False

    @staticmethod
    def _minutes(start, end):
        return max((end - start).total_seconds(), 0.0) / 60.0 if start and end else 0.0

    @api.depends("qty", "cancelled_qty", "sent_at", "started_at", "ready_at", "served_at", "target_seconds")
    def _compute_figures(self):
        for rec in self:
            net = max(rec.qty - rec.cancelled_qty, 0.0)
            target = max(rec.target_seconds or 0.0, 0.0) / 60.0
            prep = self._minutes(rec.sent_at, rec.ready_at)
            ready = bool(rec.ready_at) and net > 0
            measured = ready and target > 0
            late = measured and prep > target

            rec.net_qty = net
            rec.line_count = 1
            rec.is_measured = measured
            rec.untargeted_count = 1 if ready and not target else 0
            rec.prep_minutes = prep
            rec.target_minutes = target if measured else 0.0
            rec.diff_minutes = prep - target if measured else 0.0
            rec.is_late = late
            rec.late_lines = 1 if late else 0
            rec.late_minutes = prep - target if late else 0.0
            rec.on_time_pct = 100.0 if measured and not late else 0.0
            rec.start_minutes = self._minutes(rec.sent_at, rec.started_at)
            rec.serve_minutes = self._minutes(rec.ready_at, rec.served_at)
            if rec.served_at:
                rec.status = "served"
            elif rec.ready_at:
                rec.status = "ready"
            elif rec.started_at:
                rec.status = "preparing"
            else:
                rec.status = "waiting"

    #  averages on the right lines
    def _read_group_select(self, aggregate_spec, query):
        fname, _sep, func = aggregate_spec.partition(":")
        if func == "avg" and fname in self._AVG_POPULATION:
            def column(name):
                return self._field_to_sql(self._table, name, query)

            return SQL(
                "AVG(%s) FILTER (WHERE %s)",
                column(fname), self._AVG_POPULATION[fname](column))
        return super()._read_group_select(aggregate_spec, query)

    _AVG_POPULATION = {
        "prep_minutes": lambda col: col("is_measured"),
        "target_minutes": lambda col: col("is_measured"),
        "diff_minutes": lambda col: col("is_measured"),
        "on_time_pct": lambda col: col("is_measured"),
        "late_minutes": lambda col: col("is_late"),
        "start_minutes": lambda col: SQL("%s IS NOT NULL", col("started_at")),
        "serve_minutes": lambda col: SQL("%s IS NOT NULL AND %s IS NOT NULL", col("served_at"), col("ready_at")),
    }

    #  creation / retention
    @api.model
    def _target_seconds_for(self, prep_line, station):
        template = prep_line.product_id.product_tmpl_id
        minutes = template._kitchen_prep_minutes() or (station.default_target_minutes if station else 0.0)
        if not minutes:
            display = station.prep_display_id if station else self.env["pos.prep.display"]
            first_stage = display.stage_ids[:1]
            minutes = first_stage.alert_timer if first_stage else 0
        return (minutes or 0) * 60.0

    @api.model
    def _log_prep_lines(self, prep_lines):
        vals_list = []
        now = fields.Datetime.now()
        for line in prep_lines:
            order = line.prep_order_id.pos_order_id
            config = order.config_id
            if not config.kitchen_advanced or line.pos_order_line_id.combo_line_ids:
                continue
            station = line.station_id
            vals_list.append({
                "company_id": config.company_id.id,
                "config_id": config.id,
                "session_id": order.session_id.id,
                "pos_order_id": order.id,
                "pos_order_line_id": line.pos_order_line_id.id,
                "prep_line_id": line.id,
                "station_id": station.id,
                "product_id": line.product_id.id,
                "order_name": line.prep_order_id.order_name,
                "qty": line.quantity,
                "priority_at_send": line.prep_order_id.priority,
                "sent_at": now,
                "target_seconds": self._target_seconds_for(line, station),
            })
        return self.sudo().create(vals_list) if vals_list else self.browse()

    @api.model
    def _cron_retention(self):
        days = int(self.env["ir.config_parameter"].sudo().get_param("pos_kitchen_screen.retention_days", 365))
        limit = fields.Datetime.now() - timedelta(days=days)
        self.sudo().search([("sent_at", "<", limit)]).unlink()
        self.env["pos.kitchen.assignment.history"].sudo().search([("changed_at", "<", limit)]).unlink()
        self.env["pos.kitchen.item.history"].sudo().search([("changed_at", "<", limit)]).unlink()
        return True