from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.point_of_sale.tests.common import TestPoSCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestKitchen(TestPoSCommon):
    """NOTE: written from a static review, not executed. Run with --test-tags pos_kitchen_screen."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.config.kitchen_advanced = True
        cls.categ = cls.env['pos.category'].create({'name': 'Kitchen test category'})
        cls.product.product_tmpl_id.pos_categ_ids = [Command.link(cls.categ.id)]
        cls.display_a = cls.env['pos.prep.display'].create({
            'name': 'Main', 'pos_config_ids': [Command.link(cls.config.id)]})
        cls.display_b = cls.env['pos.prep.display'].create({
            'name': 'Grill', 'pos_config_ids': [Command.link(cls.config.id)]})
        cls.grill = cls.env['pos.kitchen.station'].create({
            'name': 'Grill', 'code': 'GRILL', 'prep_display_id': cls.display_b.id,
            'pos_config_ids': [Command.link(cls.config.id)],
            'category_ids': [Command.link(cls.categ.id)]})

    def _send(self):
        self.open_new_session()
        order = next(iter(self._create_orders([{'pos_order_lines_ui_args': [(self.product, 1)]}]).values()))
        self.env['pos.prep.order'].process_order(order.id)
        return order

    def test_product_routing(self):
        order = self._send()
        line = self.env['pos.prep.line'].search([('pos_order_line_id', '=', order.lines[0].id)])
        self.assertEqual(line.station_id, self.grill)
        states = self.env['pos.prep.state'].search([('prep_line_id', '=', line.id)])
        self.assertEqual(states.stage_id.prep_display_id, self.display_b)

    def test_flag_off_is_native(self):
        self.config.kitchen_advanced = False
        order = self._send()
        line = self.env['pos.prep.line'].search([('pos_order_line_id', '=', order.lines[0].id)])
        self.assertFalse(line.station_id)
        self.assertFalse(self.env['pos.kitchen.performance'].search([('prep_line_id', '=', line.id)]))

    def test_chef_assignment_and_readiness(self):
        order = self._send()
        line = self.env['pos.prep.line'].search([('pos_order_line_id', '=', order.lines[0].id)])
        chef = self.env['pos.kitchen.chef'].create({'user_id': self.env.user.id, 'station_ids': [Command.link(self.grill.id)]})
        line.assign_chef(chef.id)
        self.assertEqual(line.assigned_chef_id, chef)
        self.assertTrue(self.env['pos.kitchen.assignment.history'].search([('prep_line_id', '=', line.id)]))
        self.assertEqual(order.kitchen_readiness, 'in_progress')
        state = line.state_ids
        stages = self.display_b.stage_ids
        state.change_state_stage({str(state.id): stages[1].id}, self.display_b.id)
        self.assertEqual(order.kitchen_readiness, 'ready')
        self.assertTrue(order.kitchen_ready_at)
        perf = self.env['pos.kitchen.performance'].search([('prep_line_id', '=', line.id)])
        self.assertTrue(perf.ready_at)
        self.assertEqual(perf.chef_id, chef)

    def test_cancelled_lines_ignored_in_readiness(self):
        order = self._send()
        line = self.env['pos.prep.line'].search([('pos_order_line_id', '=', order.lines[0].id)])
        line.cancelled = line.quantity
        self.assertEqual(order.kitchen_readiness, 'no_items')

    def test_priority_comes_from_pos_order(self):
        self.open_new_session()
        order = next(iter(self._create_orders([{'pos_order_lines_ui_args': [(self.product, 1)]}]).values()))
        order.kitchen_priority = 'high'
        self.env['pos.prep.order'].process_order(order.id)
        ticket = self.env['pos.prep.order'].search([('pos_order_id', '=', order.id)])
        self.assertEqual(ticket.priority, 'high')
        order.set_kitchen_priority('low')
        self.assertEqual(ticket.priority, 'low')

    def test_overflow_item_wise_and_move(self):
        self.grill.workload_limit = 1
        bar = self.env['pos.kitchen.station'].create({
            'name': 'Grill 2', 'code': 'GRILL2', 'prep_display_id': self.display_a.id,
            'pos_config_ids': [Command.link(self.config.id)], 'workload_limit': 5,
            'category_ids': [Command.link(self.categ.id)]})
        self.open_new_session()
        orders = self._create_orders([
            {'pos_order_lines_ui_args': [(self.product, 1)]},
            {'pos_order_lines_ui_args': [(self.product, 1)]},
        ])
        for order in orders.values():
            self.env['pos.prep.order'].process_order(order.id)
        workload = {w['code']: w for w in self.env['pos.kitchen.station'].get_station_workload()}
        self.assertEqual(workload['GRILL']['value'], 2)
        self.assertEqual(workload['GRILL']['overflow_orders'], 1)
        self.assertIn(bar.id, workload['GRILL']['alternatives'])
        result = self.grill.move_overflow(bar.id)
        self.assertEqual(result['remaining'], 0)
        workload = {w['code']: w for w in self.env['pos.kitchen.station'].get_station_workload()}
        self.assertEqual(workload['GRILL']['value'], 1)
        self.assertEqual(workload['GRILL2']['value'], 1)

    def test_time_wise_workload_uses_category_time(self):
        self.categ.kitchen_prep_target_minutes = 4
        self.grill.write({'workload_metric': 'time', 'workload_limit': 5})
        self.open_new_session()
        orders = self._create_orders([{'pos_order_lines_ui_args': [(self.product, 2)]}])
        self.env['pos.prep.order'].process_order(next(iter(orders.values())).id)
        workload = {w['code']: w for w in self.env['pos.kitchen.station'].get_station_workload()}
        self.assertEqual(workload['GRILL']['value'], 8)
        self.assertTrue(workload['GRILL']['overloaded'])
