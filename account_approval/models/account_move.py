# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_rule_id = fields.Many2one(
        'account.approval.rule',
        string='Approval Rule',
        readonly=True
    )

    current_approval_level = fields.Integer(
        string='Current Approval Level',
        default=1
    )

    approval_history_ids = fields.One2many(
        'account.approval.history',
        'invoice_id',
        string='Approval History'
    )

    is_current_user_approver = fields.Boolean(
        string='Is Current User Approver',
        compute='_compute_is_current_user_approver'
    )

    @api.depends('state', 'approval_rule_id')
    def _compute_is_current_user_approver(self):
        for invoice in self:
            if invoice.state == 'draft':
                invoice.is_current_user_approver = True
            else:
                invoice.is_current_user_approver = False

    def action_submit_for_approval(self):
        """Submit invoice for approval"""
        for invoice in self:
            if invoice.state != 'draft':
                raise UserError(_('Only draft invoices can be submitted for approval!'))
            
            # Create history record
            self.env['account.approval.history'].create({
                'invoice_id': invoice.id,
                'user_id': self.env.user.id,
                'status': 'pending',
                'comment': 'Submitted for approval',
                'approval_level': 1
            })
            
            invoice.message_post(
                body=_('Invoice submitted for approval.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_approve(self):
        """Approve invoice"""
        for invoice in self:
            if invoice.state != 'draft':
                raise UserError(_('Only draft invoices can be approved!'))
            
            # Create history record
            self.env['account.approval.history'].create({
                'invoice_id': invoice.id,
                'user_id': self.env.user.id,
                'status': 'approved',
                'comment': 'Approved',
                'approval_level': invoice.current_approval_level
            })
            
            # Post the invoice
            invoice.action_post()
            
            invoice.message_post(
                body=_('Invoice approved and posted.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_reject(self):
        """Reject invoice"""
        for invoice in self:
            if invoice.state != 'draft':
                raise UserError(_('Only draft invoices can be rejected!'))
            
            # Create history record
            self.env['account.approval.history'].create({
                'invoice_id': invoice.id,
                'user_id': self.env.user.id,
                'status': 'rejected',
                'comment': 'Rejected',
                'approval_level': invoice.current_approval_level
            })
            
            invoice.message_post(
                body=_('Invoice rejected.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )