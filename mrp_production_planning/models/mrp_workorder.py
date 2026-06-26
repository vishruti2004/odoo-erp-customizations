# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
import logging

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    phase_material_status = fields.Selection(
        [
            ('available', 'Available'),
            ('blocked', 'Blocked'),
            ('partial', 'Partial Available'),
        ],
        string='Phase Material Status',
        compute='_compute_phase_material_status',
        default='available',
    )

    phase_component_move_ids = fields.One2many(
        comodel_name="stock.move",
        compute="_compute_phase_component_moves",
        string="Phase Components",
    )

    phase_shortage_line_ids = fields.One2many(
        'mrp.phase.material.shortage',
        'workorder_id',
        string='Phase Shortage Lines'
    )

    @api.depends(
        "operation_id",
        "production_id.move_raw_ids",
        "production_id.move_raw_ids.state",
        "production_id.move_raw_ids.bom_line_id",
    )
    def _compute_phase_component_moves(self):
        for workorder in self:
            if not workorder.operation_id or not workorder.production_id:
                workorder.phase_component_move_ids = self.env["stock.move"]
                continue

            workorder.phase_component_move_ids = workorder.production_id.move_raw_ids.filtered(
                lambda move: (
                    move.bom_line_id
                    and move.bom_line_id.operation_id == workorder.operation_id
                    and move.state not in ("done", "cancel")
                )
            )

    @api.depends('production_id.move_raw_ids', 'operation_id')
    def _compute_phase_material_status(self):
        for workorder in self:
            if not workorder.company_id.phase_wise_material_check:
                workorder.phase_material_status = 'available'
                continue

            phase_moves = workorder._get_phase_moves()
            if not phase_moves:
                workorder.phase_material_status = 'available'
                continue

            blocked = False
            partial = False

            for move in phase_moves:
                available_qty = self.env['stock.quant']._get_available_quantity(
                    move.product_id,
                    workorder.production_id.location_src_id,
                    strict=False,
                )
                available_qty = move.product_id.uom_id._compute_quantity(
                    available_qty,
                    move.product_uom,
                )

                if float_compare(available_qty, 0, precision_rounding=move.product_uom.rounding) <= 0:
                    blocked = True
                elif float_compare(available_qty, move.product_uom_qty, precision_rounding=move.product_uom.rounding) < 0:
                    partial = True

            if blocked:
                workorder.phase_material_status = 'blocked'
            elif partial:
                workorder.phase_material_status = 'partial'
            else:
                workorder.phase_material_status = 'available'

    def _set_phase_components(self):
        for workorder in self:
            if not workorder.company_id.phase_wise_material_check:
                continue

            phase_moves = workorder.production_id.move_raw_ids.filtered(
                lambda move: (
                    move.bom_line_id and
                    move.bom_line_id.operation_id == workorder.operation_id and
                    move.state not in ('done', 'cancel')
                )
            )
            phase_moves.write({
                'workorder_id': workorder.id,
            })

    def _get_phase_moves(self):
        self.ensure_one()
        return self.production_id.move_raw_ids.filtered(
            lambda move: (
                move.bom_line_id
                and move.bom_line_id.operation_id == self.operation_id
                and move.state not in ("done", "cancel")
            )
        )

    @api.model
    def _cron_check_phase_material_availability(self):
        _logger.info("Cron: Started checking phase material availability.")
        now = fields.Datetime.now()
        
        workorders = self.search([
            ("state", "not in", ("done", "cancel")),
            ("date_start", "!=", False),
        ])

        for workorder in workorders:
            company = workorder.company_id

            if not company.phase_wise_material_check:
                continue

            lead_days = company.material_availability_check_lead_days or 1
            check_datetime = fields.Datetime.subtract(
                workorder.date_start,
                days=lead_days,
            )

            if now < check_datetime:
                continue

            workorder._check_phase_material_shortage()

        _logger.info("Cron: Finished checking phase material availability.")
        return True

    def _check_phase_material_shortage(self):
        self.ensure_one()

        phase_moves = self._get_phase_moves()
        if not phase_moves:
            return True

        source_location = self.production_id.location_src_id
        shortage_values_list = []

        for move in phase_moves:
            available_qty = self.env["stock.quant"]._get_available_quantity(
                move.product_id,
                source_location,
                strict=False,
            )
            available_qty = move.product_id.uom_id._compute_quantity(
                available_qty,
                move.product_uom,
            )
            required_qty = move.product_uom_qty

            if float_compare(available_qty, required_qty, precision_rounding=move.product_uom.rounding) < 0:
                shortage_qty = required_qty - max(available_qty, 0.0)
                shortage_values_list.append({
                    "product_id": move.product_id.id,
                    "shortage_qty": shortage_qty,
                    "uom_id": move.product_uom.id,
                })

        if not shortage_values_list:
            self.env["mrp.phase.material.shortage"].search([
                ("workorder_id", "=", self.id),
                ("state", "in", ("draft", "shortage", "notified")),
            ]).write({'state': 'received'})
            self.phase_material_status = 'available'
            return True

        Shortage = self.env["mrp.phase.material.shortage"]
        email_sent = False

        for data in shortage_values_list:
            shortage = Shortage.search([
                ("workorder_id", "=", self.id),
                ("product_id", "=", data["product_id"]),
            ], limit=1)

            values = {
                "workorder_id": self.id,
                "product_id": data["product_id"],
                "shortage_qty": data["shortage_qty"],
                "uom_id": data["uom_id"],
                "state": "shortage",
            }

            if shortage:
                shortage.write(values)
            else:
                shortage = Shortage.create(values)

            shortage.action_create_or_update_rfq()

            if not email_sent and shortage._should_send_email():
                shortage._send_purchase_notification()
                Shortage.search([
                    ("workorder_id", "=", self.id),
                    ("state", "in", ("shortage", "rfq_created")),
                ]).write({
                    'state': 'notified',
                    'last_notification_date': fields.Date.today(),
                    'notification_count': shortage.notification_count + 1,
                })
                email_sent = True

        self.phase_material_status = 'blocked'
        return True

    def button_start(self, raise_on_invalid_state=False):
        for workorder in self:
            if not workorder.company_id.phase_wise_material_check:
                continue

            if workorder.working_state == 'blocked':
                raise UserError(_(
                    "Work Center '%s' is blocked. Cannot start workorder."
                ) % workorder.workcenter_id.name)

            production = workorder.production_id
            all_raw_moves = production.move_raw_ids.filtered(
                lambda move: move.state not in ("done", "cancel")
            )
            current_phase_moves = workorder._get_phase_moves()

            missing_lines = []
            for move in current_phase_moves:
                available_qty = self.env['stock.quant']._get_available_quantity(
                    move.product_id,
                    production.location_src_id,
                    strict=False,
                )
                available_qty = move.product_id.uom_id._compute_quantity(
                    available_qty,
                    move.product_uom,
                )
                if float_compare(available_qty, move.product_uom_qty,
                                 precision_rounding=move.product_uom.rounding) < 0:
                    missing_lines.append(
                        "%s (Required: %s %s | Available: %s %s)" % (
                            move.product_id.display_name,
                            move.product_uom_qty,
                            move.product_uom.name,
                            available_qty,
                            move.product_uom.name,
                        )
                    )

            if missing_lines:
                raise UserError(_(
                    "Cannot start '%s' because materials are insufficient:\n\n%s"
                ) % (workorder.name, '\n'.join('- %s' % line for line in missing_lines)))

            other_phase_moves = all_raw_moves - current_phase_moves
            if other_phase_moves:
                other_phase_moves._do_unreserve()

            if current_phase_moves:
                current_phase_moves._action_assign()

        return super().button_start(raise_on_invalid_state=raise_on_invalid_state)

    def button_finish(self):
        for workorder in self:
            if not workorder.company_id.phase_wise_material_check:
                continue

            production = workorder.production_id
            current_phase_moves = workorder._get_phase_moves()
            other_phase_moves = production.move_raw_ids.filtered(
                lambda move: (
                    move not in current_phase_moves
                    and move.state not in ("done", "cancel")
                )
            )

            for move in other_phase_moves:
                if move.quantity:
                    move._set_quantity_done(0)
                move.picked = False

            qty = production.qty_producing or production.product_qty
            for move in current_phase_moves:
                done_qty = move.product_uom.round(qty * move.unit_factor)
                move._set_quantity_done(done_qty)
                move.picked = True

            next_workorders = workorder.production_id.workorder_ids.filtered(
                lambda wo: wo.sequence > workorder.sequence
            ).sorted('sequence')

            if next_workorders:
                next_workorders[0]._check_phase_material_shortage()

        return super().button_finish()