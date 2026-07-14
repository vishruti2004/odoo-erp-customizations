# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class AccountApprovalHistory(models.Model):
    _name = 'account.approval.history'
    _description = 'Invoice Approval History'
    _order = 'create_date desc'

    invoice_id = fields.Many2one('account.move', string='Invoice', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Approver', required=True, default=lambda self: self.env.user)
    status = fields.Selection(selection=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], string='Status', required=True)
    comment = fields.Text(string='Comments')
    approval_level = fields.Integer(string='Approval Level', help='Sequence/level number at which this approval action was taken')
