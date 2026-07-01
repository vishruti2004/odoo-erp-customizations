# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.tools.float_utils import float_compare
import logging

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_confirm(self):
        result = super().action_confirm()
        
        for production in self:
            if not production.company_id.phase_wise_material_check:
                continue
            
            # Set phase components
            for workorder in production.workorder_ids:
                workorder._set_phase_components()
            
            # Reset moves
            moves = production.move_raw_ids.filtered(lambda m: m.state not in ("done", "cancel"))
            for move in moves:
                move.move_line_ids.unlink()
                move._do_unreserve()
                move._set_quantity_done(0)
                move.picked = False
        
        return result

    def _action_generate_consumption_wizard(self, consumption_issues, workorder_id=None):
        """Generate consumption warning wizard"""
        ctx = self.env.context.copy()
        lines = []
        for order, product, consumed, expected in consumption_issues:
            lines.append((0, 0, {
                'mrp_production_id': order.id,
                'product_id': product.id,
                'consumption': order.consumption,
                'product_uom_id': product.uom_id.id,
                'product_consumed_qty_uom': consumed,
                'product_expected_qty_uom': expected
            }))
        
        ctx.update({
            'default_mrp_production_ids': self.ids,
            'default_mrp_consumption_warning_line_ids': lines,
            'workorder_id': workorder_id,
        })
        
        action = self.env["ir.actions.actions"]._for_xml_id("mrp.action_mrp_consumption_warning")
        action['context'] = ctx
        return action

    def _get_consumption_issues(self):
        """Skip for 'flexible' (Allowed)"""
        issues = []
        for order in self:
            if order.consumption == 'flexible':
                continue
            for move in order.move_raw_ids.filtered(lambda m: m.state != 'cancel'):
                if float_compare(move.quantity, move.product_uom_qty, 
                                precision_rounding=move.product_uom.rounding) < 0:
                    issues.append((order, move.product_id, move.quantity, move.product_uom_qty))
        return issues