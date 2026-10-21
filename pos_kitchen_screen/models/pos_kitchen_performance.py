from datetime import timedelta

from odoo import api, fields, models


class PosKitchenPerformance(models.Model):
    _name = "pos.kitchen.performance"
    _description = "Kitchen Performance Log"
    _order = "sent_at desc, id desc"

    company_id = fields.Many2one("res.company", index=True)
    config_id = fields.Many2one("pos.config", ondelete="set null", index=True)
    session_id = fields.Many2one("pos.session", ondelete="set null", index=True)
    pos_order_id = fields.Many2one("pos.order", ondelete="set null")
    pos_order_line_id = fields.Many2one("pos.order.line", ondelete="set null")
    prep_line_id = fields.Many2one("pos.prep.line", ondelete="set null", index=True)
    station_id = fields.Many2one("pos.kitchen.station", ondelete="set null")
    chef_id = fields.Many2one("pos.kitchen.chef", ondelete="set null")
    product_id = fields.Many2one("product.product", ondelete="set null")
    order_name = fields.Char()

    qty = fields.Float()
    cancelled_qty = fields.Float()
    priority_at_send = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")], default="medium")

    sent_at = fields.Datetime(index=True)
    started_at = fields.Datetime()
    ready_at = fields.Datetime()
    served_at = fields.Datetime()
    sent_hour = fields.Integer(compute="_compute_sent_hour", store=True, string="Hour")

    prep_seconds = fields.Float("Preparation (s)", compute="_compute_durations", store=True, aggregator="avg")
    service_seconds = fields.Float("Service (s)", compute="_compute_durations", store=True, aggregator="avg")
    target_seconds = fields.Float("Target (s)")
    delay_seconds = fields.Float("Delay (s)", compute="_compute_durations", store=True, aggregator="avg")
    is_delayed = fields.Boolean(compute="_compute_durations", store=True)
    delayed_count = fields.Integer(compute="_compute_durations", store=True, string="Delayed lines")
    reprep_count = fields.Integer("Re-preparations")

    prep_minutes = fields.Float("Preparation (min)", compute="_compute_minutes", aggregator="avg")

    _station_sent_idx = models.Index("(station_id, sent_at)")

    @api.depends("sent_at")
    def _compute_sent_hour(self):
        for rec in self:
            rec.sent_hour = rec.sent_at.hour if rec.sent_at else 0

    @api.depends("sent_at", "ready_at", "served_at", "target_seconds")
    def _compute_durations(self):
        for rec in self:
            prep = service = delay = 0.0
            if rec.sent_at and rec.ready_at:
                prep = max((rec.ready_at - rec.sent_at).total_seconds(), 0.0)
            if rec.ready_at and rec.served_at:
                service = max((rec.served_at - rec.ready_at).total_seconds(), 0.0)
            if rec.target_seconds and rec.ready_at:
                delay = max(prep - rec.target_seconds, 0.0)
            rec.prep_seconds = prep
            rec.service_seconds = service
            rec.delay_seconds = delay
            rec.is_delayed = delay > 0
            rec.delayed_count = 1 if delay > 0 else 0

    @api.depends("prep_seconds")
    def _compute_minutes(self):
        for rec in self:
            rec.prep_minutes = rec.prep_seconds / 60.0

    #  creation / sync
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
