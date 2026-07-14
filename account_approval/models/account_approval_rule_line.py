# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AccountApprovalRuleLine(models.Model):
    _name = 'account.approval.rule.line'
    _description = 'Approval Rule Line'
    _order = 'sequence asc'

    rule_id = fields.Many2one('account.approval.rule', string='Approval Rule', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', required=True, default=10, help='Defines the approval order (lower number = earlier approval)')
    group_id = fields.Many2one('res.groups', string='Approval Group', required=True, help='Group responsible for approving the invoice')
    require_consent_for_all_users = fields.Boolean(string='Allow All Group Users', default=False, help='If enabled, all users of the selected approval group can approve the invoice. If disabled, only the specifically selected users below can approve.')
    user_ids = fields.Many2many('res.users', string='Approval Users', domain="[('group_ids', 'in', group_id)]", help='Select specific users from the approval group who can approve. Ignored if "Allow All Group Users" is enabled.')
    company_id = fields.Many2one('res.company', related='rule_id.company_id', string='Company', store=True)
