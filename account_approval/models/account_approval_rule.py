# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class AccountApprovalRule(models.Model):
    _name = 'account.approval.rule'
    _description = 'Invoice Approval Rule'
    _order = 'minimum_amount asc'

    name = fields.Char(string='Rule Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    move_type = fields.Selection(selection=[('out_invoice', 'Customer Invoice'), ('out_refund', 'Customer Credit Note'), ('in_invoice', 'Vendor Bill'), ('in_refund', 'Vendor Credit Note'), ('out_receipt', 'Sales Receipt'), ('in_receipt', 'Purchase Receipt')], string='Invoice Type', required=True)
    minimum_amount = fields.Monetary(string='Minimum Amount', required=True, default=0.0, currency_field='company_currency_id')
    maximum_amount = fields.Monetary(string='Maximum Amount', required=False, currency_field='company_currency_id')
    approval_type = fields.Selection(selection=[('single', 'Single Approval'), ('multi', 'Multi-Level Approval')], string='Approval Type', required=True, default='single')
    approval_line_ids = fields.One2many('account.approval.rule.line', 'rule_id', string='Approval Levels')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Company Currency', readonly=True)

    @api.constrains('company_id', 'move_type', 'minimum_amount', 'maximum_amount')
    def _check_amount_range_overlap(self):
        for rule in self:
            rule_max = rule.maximum_amount or float('inf')
 
            domain = [
                ('id', '!=', rule.id),
                ('company_id', '=', rule.company_id.id),
                ('move_type', '=', rule.move_type),
                ('minimum_amount', '<=', rule_max),
                '|',
                ('maximum_amount', '=', False),
                ('maximum_amount', '>=', rule.minimum_amount),
            ]
 
            conflicting_rule = self.search(domain, limit=1)
            if conflicting_rule:
                raise ValidationError(_(
                    'Amount range conflicts with rule "%s" for %s in %s.'
                ) % (conflicting_rule.name, rule.move_type, rule.company_id.name))
 