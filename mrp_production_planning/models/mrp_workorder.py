# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    # ========== FIELDS ==========
    phase_component_move_ids = fields.One2many(
        'stock.move', compute='_compute_phase_component_moves'
    )

    phase_shortage_line_ids = fields.One2many(
        'mrp.phase.material.shortage', 'workorder_id'
    )

    # ========== COMPUTE ==========
    @api.depends('operation_id', 'production_id.move_raw_ids')
    def _compute_phase_component_moves(self):
        for workorder in self:
            if not workorder.operation_id:
                workorder.phase_component_move_ids = self.env['stock.move']
                continue
            workorder.phase_component_move_ids = workorder.production_id.move_raw_ids.filtered(
                lambda m: m.bom_line_id and m.bom_line_id.operation_id == workorder.operation_id
                and m.state not in ('done', 'cancel')
            )

    # ========== HELPERS ==========
    def _set_phase_components(self):
        for workorder in self:
            if not workorder.company_id.phase_wise_material_check:
                continue
            moves = workorder.production_id.move_raw_ids.filtered(
                lambda m: m.bom_line_id and m.bom_line_id.operation_id == workorder.operation_id
                and m.state not in ('done', 'cancel')
            )
            moves.write({'workorder_id': workorder.id})

    def _get_phase_moves(self):
        self.ensure_one()
        return self.production_id.move_raw_ids.filtered(
            lambda m: m.bom_line_id and m.bom_line_id.operation_id == self.operation_id
            and m.state not in ('done', 'cancel')
        )

    # ========== CRON ==========
    @api.model
    def _cron_check_phase_material_availability(self):
        _logger.info("Cron: Checking phase material availability...")
        for workorder in self.search([
            ("state", "not in", ("done", "cancel")),
            ("date_start", "!=", False),
        ]):
            if not workorder.company_id.phase_wise_material_check:
                continue
            
            lead_days = workorder.company_id.material_availability_check_lead_days or 1
            check_date = fields.Datetime.subtract(workorder.date_start, days=lead_days)
            
            if fields.Datetime.now() >= check_date:
                workorder._check_phase_material_shortage()
        _logger.info("Cron: Finished.")

    # ========== MAIN LOGIC ==========
    def _check_phase_material_shortage(self):
        self.ensure_one()
        moves = self._get_phase_moves()
        if not moves:
            return True
        
        source_location = self.production_id.location_src_id
        shortage_data = []
        
        for move in moves:
            available = self.env['stock.quant']._get_available_quantity(
                move.product_id, source_location, strict=False
            )
            available = move.product_id.uom_id._compute_quantity(available, move.product_uom)
            
            if float_compare(available, move.product_uom_qty, precision_rounding=move.product_uom.rounding) < 0:
                shortage_data.append({
                    'product_id': move.product_id.id,
                    'shortage_qty': move.product_uom_qty - max(available, 0.0),
                    'uom_id': move.product_uom.id,
                })
        
        if not shortage_data:
            self.env['mrp.phase.material.shortage'].search([
                ('workorder_id', '=', self.id),
                ('state', 'in', ('draft', 'shortage', 'notified'))
            ]).write({'state': 'received'})
            return True
        
        Shortage = self.env['mrp.phase.material.shortage']
        for data in shortage_data:
            shortage = Shortage.search([
                ('workorder_id', '=', self.id), ('product_id', '=', data['product_id'])
            ], limit=1)
            
            if shortage:
                shortage.write({
                    'shortage_qty': data['shortage_qty'],
                    'uom_id': data['uom_id'],
                    'state': 'shortage'
                })
            else:
                Shortage.create({
                    'workorder_id': self.id,
                    'product_id': data['product_id'],
                    'shortage_qty': data['shortage_qty'],
                    'uom_id': data['uom_id'],
                    'state': 'shortage'
                }).action_create_or_update_rfq()
        
        all_shortages = Shortage.search([
            ('workorder_id', '=', self.id),
            ('state', 'in', ('shortage', 'rfq_created'))
        ])
        for shortage in all_shortages:
            if shortage._should_send_email():
                shortage._send_purchase_notification()
                break
        
        return True

    # ========== BUTTONS ==========
    def button_start(self, raise_on_invalid_state=False):
        for workorder in self:
            if not workorder.company_id.phase_wise_material_check:
                continue
            if workorder.working_state == 'blocked':
                raise UserError(_("Work Center '%s' is blocked.") % workorder.workcenter_id.name)
            
            production = workorder.production_id
            phase_moves = workorder._get_phase_moves()
            
            all_moves = production.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel'))
            (all_moves - phase_moves)._do_unreserve()
            phase_moves._action_assign()
            
            issues = []
            if production.consumption != 'flexible':
                for move in phase_moves:
                    if float_compare(move.quantity, move.product_uom_qty, precision_rounding=move.product_uom.rounding) < 0:
                        issues.append((production, move.product_id, move.quantity, move.product_uom_qty))
            
            if issues:
                return production._action_generate_consumption_wizard(issues, workorder.id)
        
        return super().button_start(raise_on_invalid_state=raise_on_invalid_state)

    def button_finish(self):
        for workorder in self:
            if not workorder.company_id.phase_wise_material_check:
                continue
            
            production = workorder.production_id
            phase_moves = workorder._get_phase_moves()
            other_moves = production.move_raw_ids.filtered(
                lambda m: m not in phase_moves and m.state not in ('done', 'cancel')
            )
            
            for move in other_moves:
                move._set_quantity_done(0)
                move.picked = False
            
            if self.env.context.get('skip_quantity_calculation'):
                phase_moves.picked = True
            else:
                qty = production.qty_producing or production.product_qty
                for move in phase_moves:
                    move._set_quantity_done(move.product_uom.round(qty * move.unit_factor))
                    move.picked = True
        
        return super().button_finish()