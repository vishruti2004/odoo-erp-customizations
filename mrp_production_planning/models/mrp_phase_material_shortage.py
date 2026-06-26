# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class MrpPhaseMaterialShortage(models.Model):
    _name = "mrp.phase.material.shortage"
    _description = "Phase Material Shortage"
    _order = "workorder_id, id"

    workorder_id = fields.Many2one("mrp.workorder", string="Work Order", required=True, ondelete="cascade")
    production_id = fields.Many2one("mrp.production", string="Manufacturing Order", related="workorder_id.production_id", store=True)
    product_id = fields.Many2one("product.product", string="Missing Component", required=True)
    shortage_qty = fields.Float(string="Shortage Quantity", digits="Product Unit")
    uom_id = fields.Many2one("uom.uom", string="Unit of Measure")
    state = fields.Selection([
        ("draft", "Draft"),
        ("shortage", "Shortage"),
        ("notified", "Notified"),
        ("rfq_created", "RFQ Created"),
        ("ordered", "Ordered"),
        ("received", "Received")
    ], string="Status", default="draft", copy=False)
    purchase_order_id = fields.Many2one("purchase.order", string="RFQ / Purchase Order", copy=False)
    expected_arrival_date = fields.Date(string="Expected Arrival Date", compute="_compute_expected_arrival_date", store=True)
    company_id = fields.Many2one("res.company", related="workorder_id.company_id", store=True)
    last_notification_date = fields.Date(string="Last Notification Date", copy=False)
    notification_count = fields.Integer(string="Notification Count", default=0, copy=False)

    @api.depends("purchase_order_id", "purchase_order_id.date_planned", "purchase_order_id.date_approve", "product_id")
    def _compute_expected_arrival_date(self):
        for rec in self:
            if rec.purchase_order_id:
                date = rec.purchase_order_id.date_planned or rec.purchase_order_id.date_approve
                if date:
                    rec.expected_arrival_date = date
                    continue
            supplier = rec.product_id.seller_ids[:1]
            if supplier:
                rec.expected_arrival_date = fields.Date.today() + timedelta(days=supplier.delay or 0)
                continue
            rec.expected_arrival_date = fields.Date.today() + timedelta(days=7)

    def action_create_or_update_rfq(self):
        """Create new RFQ for the shortage"""
        self.ensure_one()
        planned_date = self.workorder_id.date_start or self.production_id.date_start or fields.Datetime.now()
        
        # Search for vendor
        supplier = self.product_id._select_seller(
            partner_id=False,
            quantity=self.shortage_qty,
            date=fields.Date.today(),
            uom_id=self.uom_id
        )
        
        if not supplier:
            _logger.warning("No vendor found for %s", self.product_id.display_name)
            self.state = "shortage"
            return True
        
        partner = supplier.partner_id
        price = supplier.price or 0.0
        _logger.info("Supplier found: %s", partner.name)
        
        # Create new purchase order
        po = self.env["purchase.order"].create({
            "company_id": self.company_id.id,
            "origin": self.production_id.name,
            "partner_id": partner.id,
            "order_line": [(0, 0, {
                "product_id": self.product_id.id,
                "product_qty": self.shortage_qty,
                "product_uom_id": self.uom_id.id,
                "date_planned": planned_date,
                "price_unit": price
            })]
        })
        self.purchase_order_id = po.id
        self.state = "rfq_created"
        _logger.info("New RFQ created: %s", po.name)
        return True

    def _send_purchase_notification(self):
        """Send email notification to purchase managers including all shortages for the workorder"""
        self.ensure_one()
        
        managers = self.company_id.phase_purchase_manager_ids.filtered("partner_id")
        if not managers:
            _logger.warning("No purchase managers configured")
            return True
        
        # Get all active shortages for this workorder
        shortages = self.env['mrp.phase.material.shortage'].search([
            ('workorder_id', '=', self.workorder_id.id),
            ('state', 'in', ('shortage', 'notified', 'rfq_created'))
        ])
        
        if not shortages:
            _logger.info("No active shortages found, email not sent")
            return True
        
        template = self.env.ref(
            "mrp_production_planning.mail_template_phase_material_shortage",
            raise_if_not_found=False
        )
        
        if template:
            # Send email using the first record as the primary object
            template.sudo().with_company(self.company_id).send_mail(
                shortages[0].id,
                email_values={
                    "email_to": False,
                    "recipient_ids": [(6, 0, managers.mapped("partner_id").ids)],
                    "email_from": self.company_id.email_formatted or self.env.company.email_formatted,
                },
                force_send=False
            )
            _logger.info("Email sent to %s for %d shortage(s)", managers.mapped('name'), len(shortages))
        else:
            _logger.warning("Email template not found")
        
        return True

    def _should_send_email(self):
        """Check if email should be sent based on company configuration"""
        self.ensure_one()
        company = self.company_id
        
        if self.state == 'received':
            return False
        
        if company.shortage_email_mode == 'once':
            if self.state == 'notified':
                return False
            return True
        
        elif company.shortage_email_mode == 'repeat':
            return True
        
        return False