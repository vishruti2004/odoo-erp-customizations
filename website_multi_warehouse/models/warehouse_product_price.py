from odoo import models, fields, api

class WarehouseProductPrice(models.Model):
    _name = 'warehouse.product.price'
    _description = 'Warehouse Product Cost'

    product_id = fields.Many2one('product.product', string='Product', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', required=True)
    cost = fields.Float(string='Cost')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    def _get_price_record(self, product_variant, warehouse):
        return self.search([
            ('product_id', '=', product_variant.id),
            ('warehouse_id', '=', warehouse.id),
        ], limit=1)

    def _get_fifo_unit_cost(self, product_variant, warehouse, sale_qty=None):
        incoming_moves = self.env['stock.move'].search([
            ('product_id', '=', product_variant.id),
            ('picking_type_id.warehouse_id', '=', warehouse.id),
            ('is_in', '=', True),
            ('state', '=', 'done'),
        ], order='date asc, id asc')

        if not sale_qty:
            for move in incoming_moves:
                if move.remaining_qty > 0:
                    return move.value / move.quantity if move.quantity else 0.0
            return 0.0

        remaining_qty = sale_qty
        total_cost = 0.0
        for move in incoming_moves:
            if remaining_qty <= 0:
                break
            if move.remaining_qty <= 0:
                continue
            consumed_qty = min(move.remaining_qty, remaining_qty)
            total_cost += consumed_qty * (move.value / move.quantity if move.quantity else 0.0)
            remaining_qty -= consumed_qty

        if remaining_qty > 0 and incoming_moves:
            last_move = incoming_moves[-1]
            total_cost += remaining_qty * (last_move.value / last_move.quantity if last_move.quantity else 0.0)

        return total_cost / sale_qty if sale_qty else 0.0

    @api.model
    def _update_warehouse_cost(self, stock_move, warehouse, move_type):
        product_variant = stock_move.product_id
        cost_method = product_variant.categ_id.property_cost_method
        unit_cost = stock_move.price_unit or product_variant.standard_price
        move_qty = stock_move.quantity

        if move_type == 'incoming':
            if cost_method == 'fifo':
                self._process_fifo_incoming(product_variant, warehouse, unit_cost)
            elif cost_method == 'average':
                self._process_avco_incoming(product_variant, warehouse, unit_cost, move_qty)
            else:
                self._process_std_incoming(product_variant, warehouse, unit_cost)
        elif move_type == 'outgoing' and cost_method == 'fifo':
            self._process_fifo_outgoing(product_variant, warehouse)

    def _process_fifo_incoming(self, product_variant, warehouse, unit_cost):
        fifo_cost = self._get_fifo_unit_cost(product_variant, warehouse) or unit_cost
        price_record = self._get_price_record(product_variant, warehouse)
        if price_record:
            price_record.cost = fifo_cost
        else:
            self.create({
                'product_id': product_variant.id,
                'warehouse_id': warehouse.id,
                'cost': fifo_cost,
            })

    def _process_fifo_outgoing(self, product_variant, warehouse):
        price_record = self._get_price_record(product_variant, warehouse)
        if price_record:
            price_record.cost = self._get_fifo_unit_cost(product_variant, warehouse)

    def _process_avco_incoming(self, product_variant, warehouse, new_unit_cost, new_qty):
        price_record = self._get_price_record(product_variant, warehouse)
        if price_record:
            stock_quants = self.env['stock.quant'].search([
                ('product_id', '=', product_variant.id),
                ('location_id', 'child_of', warehouse.lot_stock_id.id),
            ])
            total_qty = sum(stock_quants.mapped('quantity'))
            old_qty = max(total_qty - new_qty, 0)
            if total_qty > 0:
                price_record.cost = ((price_record.cost * old_qty) + (new_unit_cost * new_qty)) / total_qty
        else:
            self.create({
                'product_id': product_variant.id,
                'warehouse_id': warehouse.id,
                'cost': new_unit_cost,
            })

    def _process_std_incoming(self, product_variant, warehouse, unit_cost):
        price_record = self._get_price_record(product_variant, warehouse)
        if price_record:
            price_record.cost = unit_cost
        else:
            self.create({
                'product_id': product_variant.id,
                'warehouse_id': warehouse.id,
                'cost': unit_cost,
            })