# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    phase_wise_material_check = fields.Boolean(
        string="Enable Phase-Wise Material Check",
        help="Reserve and consume raw materials operation-wise instead of for the full Manufacturing Order.",
    )

    auto_create_phase_rfq = fields.Boolean(
        string="Auto Create RFQ for Material Shortage",
        help="Automatically create or update an RFQ when a phase material shortage is detected.",
    )

    phase_purchase_manager_ids = fields.Many2many(
        "res.users",
        "res_company_phase_purchase_manager_rel",
        "company_id",
        "user_id",
        string="Phase Purchase Managers",
        help="Users who receive material shortage notifications.",
    )

    material_availability_check_lead_days = fields.Integer(
        string="Material Availability Check Lead Time (Days)",
        default=1,
        help=(
            "Number of days before the operation start date when "
            "material availability is checked and shortage notifications are sent."
        ),
    )

    # ---------------- Email Configuration ---------------- #

    send_phase_shortage_email = fields.Boolean(
        string="Send Material Shortage Email",
        default=True,
        help="Send email notifications when material shortage is detected.",
    )

    shortage_email_mode = fields.Selection(
        [
            ("once", "Send Only Once"),
            ("repeat", "Repeat Until Stock Arrives"),
        ],
        string="Email Notification Mode",
        default="once",
        help="Choose whether the shortage email should be sent only once or repeatedly until stock becomes available.",
    )