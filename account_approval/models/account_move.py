# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    approval_rule_id = fields.Many2one('account.approval.rule', string='Approval Rule', readonly=True)
    current_approval_level = fields.Integer(string='Current Approval Level', default=1)
    approval_history_ids = fields.One2many('account.approval.history', 'invoice_id', string='Approval History')
    is_current_user_approver = fields.Boolean(string='Is Current User Approver', compute='_compute_is_current_user_approver')
    is_approval_manager = fields.Boolean(string='Is Approval Manager', compute='_compute_is_approval_manager')
    approval_history_display_ids = fields.Many2many(
        'account.approval.history',
        compute='_compute_approval_history_display_ids',
        string='Approval History (Filtered)',
        readonly=True
    )
    portal_status_label = fields.Char(string='Portal Status Label', compute='_compute_portal_status_display')
    portal_status_class = fields.Char(string='Portal Status Class', compute='_compute_portal_status_display')

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

    @api.depends('approval_rule_id')
    def _compute_is_approval_manager(self):
        for invoice in self:
            rule = invoice.approval_rule_id
            if not rule:
                invoice.is_approval_manager = False
                continue

            all_approvers = self.env['res.users']
            for level in rule.approval_line_ids:
                all_approvers |= invoice._get_level_approvers(level)

            invoice.is_approval_manager = self.env.user in all_approvers

    @api.depends('approval_history_ids', 'approval_history_ids.status', 'is_approval_manager')
    def _compute_approval_history_display_ids(self):
        for invoice in self:
            if invoice.is_approval_manager:
                invoice.approval_history_display_ids = invoice.approval_history_ids
            else:
                invoice.approval_history_display_ids = invoice.approval_history_ids.filtered(
                    lambda h: h.status != 'pending'
                )

    @api.depends('state')
    def _compute_portal_status_display(self):
        mapping = {
            'draft': (_('Draft'), 'text-bg-secondary'),
            'waiting': (_('Waiting for Approval'), 'text-bg-warning'),
            'partially_approved': (_('Partially Approved'), 'text-bg-info'),
            'approved': (_('Approved'), 'text-bg-primary'),
            'posted': (_('Posted'), 'text-bg-success'),
            'rejected': (_('Rejected'), 'text-bg-danger'),
            'cancel': (_('Cancelled'), 'text-bg-secondary'),
        }
        for invoice in self:
            label, css_class = mapping.get(invoice.state, (invoice.state, 'text-bg-secondary'))
            invoice.portal_status_label = label
            invoice.portal_status_class = css_class

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
        if not level:
            return self.env['res.users']
        if level.user_ids:
            return level.user_ids
        return self._get_group_users(level.group_id)

    def _get_approved_users_for_level(self, level_sequence):
        self.ensure_one()
        history = self.env['account.approval.history'].search([
            ('invoice_id', '=', self.id),
            ('approval_level', '=', level_sequence),
            ('status', '=', 'approved'),
        ])
        return history.mapped('user_id')

    def _is_level_fully_approved(self, level):
        self.ensure_one()
        if not level:
            return False
        required_users = self._get_level_approvers(level)
        approved_users = self._get_approved_users_for_level(self.current_approval_level)
        return bool(required_users) and required_users <= approved_users

    def _create_pending_history_for_level(self, level):
        self.ensure_one()
        approvers = self._get_level_approvers(level)
        level_number = self._level_sequence_for(level)
        for approver in approvers:
            self.env['account.approval.history'].create({
                'invoice_id': self.id,
                'user_id': approver.id,
                'status': 'pending',
                'comment': 'Waiting for approval',
                'approval_level': level_number,
            })

    def _level_sequence_for(self, level):
        self.ensure_one()
        level_lines = self.approval_rule_id.approval_line_ids.sorted('sequence')
        return list(level_lines).index(level) + 1

    def _create_pending_history_for_all_levels(self):
        self.ensure_one()
        rule = self.approval_rule_id
        if not rule:
            return
        for level in rule.approval_line_ids.sorted('sequence'):
            self._create_pending_history_for_level(level)

    def _record_approval_history(self, status, comment):
        self.ensure_one()
        own_pending = self.env['account.approval.history'].search([
            ('invoice_id', '=', self.id),
            ('status', '=', 'pending'),
            ('approval_level', '=', self.current_approval_level),
            ('user_id', '=', self.env.user.id),
        ], limit=1)

        if own_pending:
            own_pending.write({
                'status': status,
                'comment': comment or status.capitalize(),
            })
        else:
            self.env['account.approval.history'].create({
                'invoice_id': self.id,
                'user_id': self.env.user.id,
                'status': status,
                'comment': comment or status.capitalize(),
                'approval_level': self.current_approval_level
            })

        level = self._get_current_level()
        if level and not level.require_consent_for_all_users:
            other_pending = self.env['account.approval.history'].search([
                ('invoice_id', '=', self.id),
                ('status', '=', 'pending'),
                ('approval_level', '=', self.current_approval_level),
                ('user_id', '!=', self.env.user.id),
            ])
            other_pending.unlink()

    def action_post(self):
        admin_direct = self.browse()
        no_rule_direct = self.browse()
        other_direct = self.browse()
        to_approval = self.browse()

        for invoice in self:
            if invoice.state != 'draft' or invoice.move_type not in ('out_invoice', 'in_invoice', 'out_refund', 'in_refund'):
                other_direct |= invoice
                continue

            if invoice._is_admin_user():
                admin_direct |= invoice
                continue

            matching_rule = invoice._get_matching_approval_rule()

            if not matching_rule:
                no_rule_direct |= invoice
                continue

            invoice.approval_rule_id = matching_rule.id
            invoice.current_approval_level = 1
            invoice.state = 'waiting'

            invoice._create_pending_history_for_all_levels()

            invoice._send_approval_notification()
            to_approval |= invoice

        direct_post = admin_direct | no_rule_direct | other_direct
        if direct_post:
            super(AccountMove, direct_post).action_post()

        for invoice in admin_direct:
            invoice.message_post(
                body=_('Invoice posted directly by Administrator (approval workflow bypassed).'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

        for invoice in no_rule_direct:
            invoice.message_post(
                body=_('Invoice posted directly (no approval rule matched).'),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

    def button_draft(self):
        rejected = self.filtered(lambda m: m.state == 'rejected')
        others = self - rejected

        if rejected:
            for invoice in rejected:
                invoice.approval_history_ids.unlink()
            rejected.write({
                'state': 'draft',
                'approval_rule_id': False,
                'current_approval_level': 1,
            })
            for invoice in rejected:
                invoice.message_post(
                    body=_('Invoice reset to draft. The approval process will restart on next submission.'),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note'
                )

        if others:
            super(AccountMove, others).button_draft()

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

        if self.state not in ('waiting', 'partially_approved'):
            raise UserError(_('Invoice is not waiting for approval!'))
        if not self.approval_rule_id:
            raise UserError(_('No approval rule found for this invoice!'))
        if not self._check_user_approver():
            raise UserError(_('You are not authorized to approve this invoice!'))

        level_lines = self.approval_rule_id.approval_line_ids.sorted('sequence')
        level = self._get_current_level()

        if level.require_consent_for_all_users:
            already_approved = self._get_approved_users_for_level(self.current_approval_level)
            if self.env.user in already_approved:
                raise UserError(_('You have already approved this invoice at this level!'))

        self._record_approval_history('approved', comment)

        if level.require_consent_for_all_users:
            if not self._is_level_fully_approved(level):
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

            self.message_post(
                body=_('Invoice approved at level %s. Moving to level %s.') %
                (self.current_approval_level - 1, self.current_approval_level),
                message_type='notification',
                subtype_xmlid='mail.mt_note'
            )

            self._send_approval_notification()

    def reject_with_comment(self, comment):
        self.ensure_one()

        if self.state not in ('waiting', 'partially_approved'):
            raise UserError(_('Invoice is not waiting for approval!'))
        if not self.approval_rule_id:
            raise UserError(_('No approval rule found for this invoice!'))
        if not self._check_user_approver():
            raise UserError(_('You are not authorized to reject this invoice!'))

        self.state = 'rejected'

        self._record_approval_history('rejected', comment)
        self.env['account.approval.history'].search([
            ('invoice_id', '=', self.id),
            ('status', '=', 'pending'),
        ]).unlink()

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