# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class AccountApprovalCommentWizard(models.TransientModel):
    _name = 'account.approval.comment.wizard'
    _description = 'Approval Comment Wizard'

    invoice_id = fields.Many2one('account.move', string='Invoice', required=True)
    action_type = fields.Selection(
        selection=[('approve', 'Approve'), ('reject', 'Reject')],
        string='Action',
        required=True
    )
    comment = fields.Text(string='Comment',required=True,help='Add your remarks.')
    def action_confirm(self):
        self.ensure_one()

        if self.action_type == 'approve':
            self.invoice_id.approve_with_comment(self.comment)
        else:
            self.invoice_id.reject_with_comment(self.comment)

        return {'type': 'ir.actions.act_window_close'}