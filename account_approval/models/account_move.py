# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_rule_id = fields.Many2one('account.approval.rule', string='Approval Rule', readonly=True)
    current_approval_level = fields.Integer(string='Current Approval Level', default=1)
    approval_history_ids = fields.One2many('account.approval.history', 'invoice_id', string='Approval History')
    is_current_user_approver = fields.Boolean(string='Is Current User Approver', compute='_compute_is_current_user_approver')

    state = fields.Selection(
        selection_add=[
            ('waiting', 'Waiting for Approval'),
            ('partially_approved', 'Partially Approved'),
            ('approved', 'Approved'),
            ('posted',),
            ('rejected', 'Rejected'),
        ],
        ondelete={
            'waiting': lambda recs: recs.write({'state': 'draft'}),
            'partially_approved': lambda recs: recs.write({'state': 'draft'}),
            'approved': lambda recs: recs.write({'state': 'posted'}),
            'rejected': lambda recs: recs.write({'state': 'cancel'}),
        }
    )

    @api.depends('state')
    def _compute_status_in_payment(self):
        for move in self:
            if move.state in ['waiting', 'partially_approved', 'approved', 'rejected']:
                move.status_in_payment = 'draft'
            else:
                move.status_in_payment = move.state

    @api.depends('state', 'approval_rule_id')
    def _compute_is_current_user_approver(self):
        for invoice in self:
            if invoice.state in ['waiting', 'partially_approved']:
                invoice.is_current_user_approver = invoice._check_user_approver()
            else:
                invoice.is_current_user_approver = False

    def _get_matching_approval_rule(self):
        self.ensure_one()
        if self.move_type not in ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']:
            return False
        domain = [
            ('company_id', '=', self.company_id.id),
            ('move_type', '=', self.move_type),
            ('minimum_amount', '<=', self.amount_total),
        ]
        rules = self.env['account.approval.rule'].search(domain)
        for rule in rules:
            if not rule.maximum_amount or self.amount_total <= rule.maximum_amount:
                return rule
        return False

    def _get_group_users(self, group):
        if not group:
            return self.env['res.users']
        User = self.env['res.users']
        if 'group_ids' in User._fields:
            return User.search([('group_ids', 'in', group.id)])
        else:
            return User.search([('groups_id', 'in', group.id)])

    def _is_admin_user(self):
        return self.env.user.has_group('base.group_system')

    def _get_current_level(self):
        self.ensure_one()
        rule = self.approval_rule_id
        if not rule:
            return self.env['account.approval.rule.line']
        level_lines = rule.approval_line_ids.sorted('sequence')
        current_level_idx = self.current_approval_level - 1
        if current_level_idx >= len(level_lines):
            return self.env['account.approval.rule.line']
        return level_lines[current_level_idx]

    def _get_level_approvers(self, level):
        """All eligible approvers for a level"""
        if not level:
            return self.env['res.users']
        if level.user_ids:
            return level.user_ids
        return self._get_group_users(level.group_id)

    def _get_approved_users_for_level(self, level_sequence):
        """Users who have already recorded an approved history entry
        for the given approval level of this invoice."""
        self.ensure_one()
        history = self.env['account.approval.history'].search([
            ('invoice_id', '=', self.id),
            ('approval_level', '=', level_sequence),
            ('status', '=', 'approved'),
        ])
        return history.mapped('user_id')

    def _is_level_fully_approved(self, level):
        """True when every required approverhas approved."""
        self.ensure_one()
        if not level:
            return False
        required_users = self._get_level_approvers(level)
        approved_users = self._get_approved_users_for_level(self.current_approval_level)
        return bool(required_users) and required_users <= approved_users

    def _record_approval_history(self, status, comment):
        self.ensure_one()
        pending_history = self.env['account.approval.history'].search([
            ('invoice_id', '=', self.id),
            ('status', '=', 'pending'),
            ('approval_level', '=', self.current_approval_level)
        ], limit=1)
        if pending_history:
            pending_history.write({
                'status': status,
                'comment': comment or status.capitalize(),
                'user_id': self.env.user.id,
            })
        else:
            self.env['account.approval.history'].create({
                'invoice_id': self.id,
                'user_id': self.env.user.id,
                'status': status,
                'comment': comment or status.capitalize(),
                'approval_level': self.current_approval_level
            })

    def action_submit_for_approval(self):
        for invoice in self:
            if invoice.state not in ['draft', 'rejected']:
                raise UserError(_('Only draft or rejected invoices can be submitted for approval!'))

            if invoice._is_admin_user():
                invoice.action_post()
                invoice.message_post(
                    body=_('Invoice posted directly by Administrator (approval workflow bypassed).'),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
                continue

            matching_rule = invoice._get_matching_approval_rule()

            if not matching_rule:
                invoice.action_post()
                invoice.message_post(
                    body=_('Invoice posted directly (no approval rule matched).'),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
                continue

            self._send_approval_notification()

            invoice.message_post(
                body=_('Invoice submitted for approval. Rule: %s (Level 1)') % matching_rule.name,
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def action_approve(self):
        self.ensure_one()
        if self.state not in ['waiting', 'partially_approved']:
            raise UserError(_('Invoice is not waiting for approval!'))
        if not self.approval_rule_id:
            raise UserError(_('No approval rule found for this invoice!'))
        if not self._check_user_approver():
            raise UserError(_('You are not authorized to approve this invoice!'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Approval Comment'),
            'res_model': 'account.approval.comment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_action_type': 'approve',
            },
        }

    def action_reject(self):
        self.ensure_one()
        if self.state not in ['waiting', 'partially_approved']:
            raise UserError(_('Invoice is not waiting for approval!'))
        if not self.approval_rule_id:
            raise UserError(_('No approval rule found for this invoice!'))
        if not self._check_user_approver():
            raise UserError(_('You are not authorized to reject this invoice!'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rejection Comment'),
            'res_model': 'account.approval.comment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_invoice_id': self.id,
                'default_action_type': 'reject',
            },
        }

    def approve_with_comment(self, comment):
        self.ensure_one()
        level_lines = self.approval_rule_id.approval_line_ids.sorted('sequence')
        level = self._get_current_level()

        if level.require_consent_for_all_users:
            already_approved = self._get_approved_users_for_level(self.current_approval_level)
            if self.env.user in already_approved:
                raise UserError(_('You have already approved this invoice at this level!'))

        self._record_approval_history('approved', comment)

        if level.require_consent_for_all_users:
            if not self._is_level_fully_approved(level):
                self.message_post(
                    body=_('Approved by %s. Waiting for the remaining approvers at level %s before this level is complete.')
                    % (self.env.user.name, self.current_approval_level),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )
                return
        else:
            self._send_decision_notification('approved')

        if self.current_approval_level >= len(level_lines):
            self.state = 'approved'
            self.action_post()
            self.message_post(
                body=_('Invoice fully approved and posted.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )
        else:
            self.current_approval_level += 1
            self.state = 'partially_approved'

            self.env['account.approval.history'].create({
                'invoice_id': self.id,
                'user_id': self.env.user.id,
                'status': 'pending',
                'comment': 'Waiting for approval at level %s' % self.current_approval_level,
                'approval_level': self.current_approval_level
            })

            self.message_post(
                body=_('Invoice approved at level %s. Moving to level %s.') %
                (self.current_approval_level - 1, self.current_approval_level),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

            self._send_approval_notification()

    def reject_with_comment(self, comment):
        self.ensure_one()
        self.state = 'rejected'

        self._record_approval_history('rejected', comment)
        self._send_decision_notification('rejected')

        self.message_post(
            body=_('Invoice rejected at level %s. Reason: %s') %
            (self.current_approval_level, comment or 'No reason provided'),
            message_type='notification',
            subtype_xmlid='mail.mt_note'
        )

    def _check_user_approver(self):
        self.ensure_one()
        level = self._get_current_level()
        if not level:
            return False
        if self.env.user not in self._get_level_approvers(level):
            return False
        if level.require_consent_for_all_users:
            already_approved = self._get_approved_users_for_level(self.current_approval_level)
            if self.env.user in already_approved:
                return False
        return True

    def _send_approval_notification(self):
        self.ensure_one()
        level = self._get_current_level()
        if not level:
            return
        approvers = self._get_level_approvers(level)
        if not approvers:
            return
        partner_ids = approvers.mapped('partner_id').ids
        if not partner_ids:
            return
        template = self.env.ref('account_approval.email_template_approval_notification', raise_if_not_found=False)
        if template:
            template.send_mail(
                self.id,
                force_send=True,
                email_values={
                    'email_to': False,
                    'recipient_ids': [(6, 0, partner_ids)],
                }
            )

    def _send_decision_notification(self, action):
        self.ensure_one()
        level = self._get_current_level()
        if not level:
            return
        # everyone must approve anyway, so a per-approval decision email is not sent.
        if level.require_consent_for_all_users:
            return
        other_approvers = self._get_level_approvers(level) - self.env.user
        if not other_approvers:
            return
        partner_ids = other_approvers.mapped('partner_id').ids
        if not partner_ids:
            return
        template = self.env.ref('account_approval.email_template_approval_decision', raise_if_not_found=False)
        if template:
            template.with_context(
                action_text=action,
                approver_name=self.env.user.name,
            ).send_mail(
                self.id,
                force_send=True,
                email_values={
                    'email_to': False,
                    'recipient_ids': [(6, 0, partner_ids)],
                },
                email_layout_xmlid='mail.mail_notification_layout'
            )