# -*- coding: utf-8 -*-
from odoo import _, fields, models, api
import logging

_logger = logging.getLogger(__name__)

class MrpConsumptionWarning(models.TransientModel):
    _inherit = 'mrp.consumption.warning'

    workorder_id = fields.Many2one('mrp.workorder', string='Work Order')

    @api.model
    def default_get(self, fields_list):
        """Set workorder_id from context"""
        defaults = super().default_get(fields_list)
        workorder_id = self.env.context.get('workorder_id')
        if workorder_id:
            defaults['workorder_id'] = workorder_id
        return defaults

    def action_confirm(self):
        """Confirm consumption warning"""
        if self.workorder_id:
            return self.workorder_id.button_finish()

        ctx = dict(self.env.context)
        ctx.pop('default_mrp_production_ids', None)
        return self.mrp_production_ids.with_context(ctx, skip_consumption=True).button_mark_done()

    def action_set_qty(self):
        """Set quantities and finish workorder"""
        if not self.workorder_id:
            return super().action_set_qty()

        # Set quantity for each line
        for line in self.mrp_consumption_warning_line_ids:
            move = line.mrp_production_id.move_raw_ids.filtered(
                lambda m: m.product_id == line.product_id
            )[:1]
            if move:
                move._set_quantity_done(line.product_consumed_qty_uom)
                move.picked = True

        # Finish workorder with skip flag
        return self.workorder_id.with_context(
            skip_quantity_calculation=True
        ).button_finish()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}