from odoo import fields, models
from odoo.tools import float_compare

class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    def _is_full_margin(self):
        self.ensure_one()
        return (
            self.product_id.type == 'consu'
            and self.product_id.is_storable
            and self.order_id.state != 'cancel'
            and float_compare(self.margin_percent, 1.0, precision_digits=4) == 0
        )        

    def _repair_total_cost(self):
        updated = self.browse()
        for line in self:
            unit_cost = line._get_repair_unit_cost()
            if unit_cost:
                line.write({'total_cost': line.qty * unit_cost, 'is_total_cost_computed': True})
                updated |= line
        return updated

    def _get_repair_unit_cost(self):
        self.ensure_one()
        origin = self.refunded_orderline_id
        if origin.qty and not origin._is_full_margin():
            return origin.total_cost / origin.qty
        return self.product_id.sudo().cost_currency_id._convert(
            from_amount=self._get_receipt_unit_cost(),
            to_currency=self.currency_id,
            company=self.company_id or self.env.company,
            date=self.order_id.date_order or fields.Date.today(),
            round=False,
        )

    def _get_receipt_unit_cost(self):
        self.ensure_one()
        receipts = self.env['stock.move'].search([
            ('product_id', '=', self.product_id.id),
            ('company_id', '=', self.company_id.id),
            ('is_in', '=', True),
            ('purchase_line_id', '!=', False),
        ], order='date desc')

        lot_names = self.pack_lot_ids.filtered('lot_name').mapped('lot_name')
        lot_move_lines = receipts.move_line_ids.filtered(lambda ml: ml.lot_id.name in lot_names)
        prices = [move_lines.move_id._get_price_unit() for move_lines in lot_move_lines.grouped('lot_id').values()]
        prices = [price for price in prices if price]
        if prices:
            return sum(prices) / len(prices)

        receipt = receipts.filtered(lambda move: move.date <= self.order_id.date_order)[:1] or receipts[-1:]
        return receipt._get_price_unit()
