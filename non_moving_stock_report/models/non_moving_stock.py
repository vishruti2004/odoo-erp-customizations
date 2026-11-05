# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class NonMovingStockReport(models.Model):
    _name = "non.moving.stock.report"
    _description = "Non-Moving Stock Report"
    _auto = False
    _rec_name = "product_id"
    _order = "last_move_date, product_id, lot_id"

    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    lot_id = fields.Many2one("stock.lot", string="Lot/Serial Number", readonly=True)
    categ_id = fields.Many2one("product.category", string="Product Category", readonly=True)
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    quantity_on_hand = fields.Float(string="On Hand", readonly=True)
    reserved_quantity = fields.Float(string="Reserved", readonly=True)
    available_quantity = fields.Float(string="Available", readonly=True)
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    value = fields.Monetary(string="Value", compute="_compute_value", groups="stock.group_stock_manager")
    purchase_date = fields.Date(string="Purchase Date", readonly=True)
    last_sale_date = fields.Datetime(string="Last Delivery Date", readonly=True)
    last_move_date = fields.Datetime(string="Last Movement Date", readonly=True)
    days_since_sale = fields.Integer(string="Days Since Last Delivery", compute="_compute_days_since_sale")

    @api.depends("last_sale_date")
    def _compute_days_since_sale(self):
        today = fields.Date.today()
        for record in self:
            record.days_since_sale = (today - record.last_sale_date.date()).days if record.last_sale_date else 0

    def _compute_value(self):
        quants = self.env["stock.quant"].search([
            ("product_id", "in", self.product_id.ids),
            ("company_id", "in", self.company_id.ids),
            ("location_id.usage", "=", "internal"),
        ])
        values = {}
        for quant in quants:
            key = (quant.product_id.id, quant.lot_id.id, quant.company_id.id)
            values[key] = values.get(key, 0) + quant.value
        for record in self:
            record.value = values.get((record.product_id.id, record.lot_id.id, record.company_id.id), 0)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            '''
            CREATE VIEW non_moving_stock_report AS (
                SELECT
                    MIN(q.id) AS id,
                    q.product_id AS product_id,
                    q.lot_id AS lot_id,
                    q.company_id AS company_id,
                    pt.categ_id AS categ_id,
                    SUM(q.quantity) AS quantity_on_hand,
                    SUM(q.reserved_quantity) AS reserved_quantity,
                    SUM(q.quantity - q.reserved_quantity) AS available_quantity,
                    last_purchase.purchase_date::date AS purchase_date,
                    last_delivery.last_sale_date AS last_sale_date,
                    COALESCE(last_delivery.last_sale_date, MIN(q.in_date)) AS last_move_date
                FROM stock_quant q
                JOIN product_product pp
                    ON pp.id = q.product_id
                JOIN product_template pt
                    ON pt.id = pp.product_tmpl_id
                JOIN stock_location loc
                    ON loc.id = q.location_id
                LEFT JOIN (
                    SELECT
                        sml.product_id,
                        sml.company_id,
                        sml.lot_id,
                        MAX(sm.date) AS last_sale_date
                    FROM stock_move_line sml
                    JOIN stock_move sm
                        ON sm.id = sml.move_id
                    JOIN stock_location source_loc
                        ON source_loc.id = sm.location_id
                    JOIN stock_location dest_loc
                        ON dest_loc.id = sm.location_dest_id
                    WHERE sm.state = 'done'
                      AND sm.sale_line_id IS NOT NULL
                      AND source_loc.usage = 'internal'
                      AND dest_loc.usage = 'customer'
                    GROUP BY sml.product_id, sml.company_id, sml.lot_id
                ) last_delivery
                    ON last_delivery.product_id = q.product_id
                   AND last_delivery.company_id = q.company_id
                   AND last_delivery.lot_id IS NOT DISTINCT FROM q.lot_id
                LEFT JOIN (
                    SELECT
                        sml.product_id,
                        sml.company_id,
                        sml.lot_id,
                        MAX(sml.date) AS purchase_date
                    FROM stock_move_line sml
                    JOIN stock_move sm
                        ON sm.id = sml.move_id
                    JOIN stock_location source_loc
                        ON source_loc.id = sm.location_id
                    JOIN stock_location dest_loc
                        ON dest_loc.id = sm.location_dest_id
                    WHERE sm.state = 'done'
                      AND source_loc.usage IN ('supplier', 'inventory', 'production')
                      AND dest_loc.usage = 'internal'
                    GROUP BY sml.product_id, sml.company_id, sml.lot_id
                ) last_purchase
                    ON last_purchase.product_id = q.product_id
                   AND last_purchase.company_id = q.company_id
                   AND last_purchase.lot_id IS NOT DISTINCT FROM q.lot_id
                WHERE loc.usage = 'internal'
                  AND q.company_id IS NOT NULL
                GROUP BY
                    q.product_id,
                    q.lot_id,
                    q.company_id,
                    pt.categ_id,
                    last_delivery.last_sale_date,
                    last_purchase.purchase_date
                HAVING SUM(q.quantity - q.reserved_quantity) > 0
            )
            '''
        )