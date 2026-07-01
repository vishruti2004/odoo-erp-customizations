# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)

class MrpPhaseMaterialShortage(models.Model):
    _name = "mrp.phase.material.shortage"
    _description = "Phase Material Shortage"
    _order = "workorder_id, id"

    workorder_id = fields.Many2one("mrp.workorder", required=True, ondelete="cascade")
    production_id = fields.Many2one("mrp.production", related="workorder_id.production_id", store=True)
    product_id = fields.Many2one("product.product", required=True)
    shortage_qty = fields.Float(digits="Product Unit")
    uom_id = fields.Many2one("uom.uom")
    
    state = fields.Selection([
        ("draft", "Draft"),
        ("shortage", "Shortage"),
        ("notified", "Notified"),
        ("rfq_created", "RFQ Created"),
        ("received", "Received")
    ], default="draft", copy=False)
    
    purchase_order_id = fields.Many2one("purchase.order", copy=False)
    company_id = fields.Many2one("res.company", related="workorder_id.company_id", store=True)
    
    # Flags
    rfq_created = fields.Boolean(default=False, copy=False)
    email_sent = fields.Boolean(default=False, copy=False)

    # ========== RFQ ==========
    def action_create_or_update_rfq(self):
        self.ensure_one()
        if self.rfq_created:
            return True
        
        supplier = self.product_id.seller_ids.filtered(
            lambda s: not s.product_id or s.product_id == self.product_id
        ).sorted(lambda s: s.price)[:1]
        
        if not supplier:
            self.state = "shortage"
            return True
        
        po = self.env["purchase.order"].create({
            "company_id": self.company_id.id,
            "origin": self.production_id.name,
            "partner_id": supplier.partner_id.id,
            "order_line": [(0, 0, {
                "product_id": self.product_id.id,
                "product_qty": self.shortage_qty,
                "product_uom_id": self.uom_id.id,
                "date_planned": self.workorder_id.date_start or fields.Datetime.now(),
                "price_unit": supplier.price or 0.0
            })]
        })
        
        self.write({
            'purchase_order_id': po.id,
            'state': 'rfq_created',
            'rfq_created': True
        })
        _logger.info("RFQ: %s for %s", po.name, self.product_id.name)
        return True

    # ========== EMAIL ==========
    def _send_purchase_notification(self):
        self.ensure_one()
        if self.email_sent:
            return True
        
        managers = self.company_id.phase_purchase_manager_ids.filtered("partner_id")
        if not managers:
            _logger.warning("No purchase managers configured")
            return True
        
        shortages = self.search([
            ('workorder_id', '=', self.workorder_id.id),
            ('state', 'in', ('shortage', 'rfq_created'))
        ])
        
        template = self.env.ref(
            "mrp_production_planning.mail_template_phase_material_shortage",
            raise_if_not_found=False
        )
        
        if template:
            template.send_mail(
                shortages[0].id,
                email_values={
                    "recipient_ids": [(6, 0, managers.mapped("partner_id").ids)],
                    "email_from": self.company_id.email_formatted or self.env.company.email_formatted,
                },
                force_send=True
            )
            shortages.write({
                'state': 'notified',
                'email_sent': True,
            })
            _logger.info(" Email sent for %s", self.product_id.name)
        return True

    def _should_send_email(self):
        self.ensure_one()
        
        if self.email_sent or self.state == 'received':
            return False
        
        move = self.workorder_id._get_phase_moves().filtered(
            lambda m: m.product_id == self.product_id
        )[:1]
        
        if not move:
            return False
        
        available = self.env['stock.quant']._get_available_quantity(
            self.product_id,
            self.workorder_id.production_id.location_src_id,
            strict=False,
        )
        available = self.product_id.uom_id._compute_quantity(available, self.uom_id)
        
        if available >= move.product_uom_qty:
            self.state = 'received'
            return False
        
        return self.company_id.shortage_email_mode in ('once', 'repeat')