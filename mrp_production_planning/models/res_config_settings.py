# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    phase_wise_material_check = fields.Boolean(
        related="company_id.phase_wise_material_check",
        readonly=False,
    )

    auto_create_phase_rfq = fields.Boolean(
        related="company_id.auto_create_phase_rfq",
        readonly=False,
    )

    phase_purchase_manager_ids = fields.Many2many(
        related="company_id.phase_purchase_manager_ids",
        readonly=False,
    )

    material_availability_check_lead_days = fields.Integer(
        related="company_id.material_availability_check_lead_days",
        string="Material Availability Check Lead Time (Days)",
        readonly=False,
    )

    # ---------------- Email Configuration ---------------- #

    send_phase_shortage_email = fields.Boolean(
        related="company_id.send_phase_shortage_email",
        readonly=False,
    )

    shortage_email_mode = fields.Selection(
        related="company_id.shortage_email_mode",
        readonly=False,
    )