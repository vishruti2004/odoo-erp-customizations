# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AccountApprovalRule(models.Model):
    _name = 'account.approval.rule'
    _description = 'Invoice Approval Rule'
    _order = 'minimum_amount asc'

    name = fields.Char(
        string='Rule Name',
        required=True,
        help='Name of the approval rule'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company for which the rule is applicable'
    )

    move_type = fields.Selection(
        selection='_selection_move_type',  
        string='Invoice Type',
        required=True,
        help='Select the invoice type for this approval rule'
    )


    minimum_amount = fields.Monetary(
        string='Minimum Amount',
        required=True,
        default=0.0,
        help='Approval workflow starts when invoice amount >= this amount',
        currency_field='company_currency_id'
    )

    maximum_amount = fields.Monetary(
        string='Maximum Amount',
        required=False,
        help='Optional maximum amount limit for the approval rule',
        currency_field='company_currency_id'
    )

    approval_type = fields.Selection(
        selection=[
            ('single', 'Single Approval'),
            ('multi', 'Multi-Level Approval'),
        ],
        string='Approval Type',
        required=True,
        default='single',
        help='Single Approval: One approver, Multi-Level: Sequential approvers'
    )

    approval_line_ids = fields.One2many(
        'account.approval.rule.line',
        'rule_id',
        string='Approval Levels',
        help='Configure the approval sequence'
    )

    company_currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Company Currency',
        readonly=True
    )

    
    def _selection_move_type(self):
        return self.env['account.move']._fields['move_type'].selection

    @api.constrains('approval_type', 'approval_line_ids')
    def _check_approval_lines_count(self):
        for rule in self:
            if not rule.approval_line_ids:
                raise ValidationError(_(
                    "Rule '%s' must have at least one Approval Level configured."
                ) % rule.name)

            if rule.approval_type == 'single' and len(rule.approval_line_ids) > 1:
                raise ValidationError(_(
                    "Rule '%s' is set to 'Single Approval' but has %d approval "
                    "levels configured. Single Approval permits only one level. "
                    "Remove the extra levels, or change Approval Type to "
                    "'Multi-Level Approval'."
                ) % (rule.name, len(rule.approval_line_ids)))