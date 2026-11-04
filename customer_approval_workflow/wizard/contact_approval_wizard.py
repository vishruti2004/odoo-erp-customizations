from odoo import _, fields, models
from odoo.tools.misc import clean_context


class ContactApprovalWizard(models.TransientModel):
    _name = 'contact.approval.wizard'
    _description = 'Contact Approval Wizard'

    partner_ids = fields.Many2many('res.partner', string='Contacts')
    decision = fields.Selection([
        ('draft', 'Set to Draft'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ], string='Action', required=True, default='approve')

    def action_confirm(self):
        self.ensure_one()
        target_state = {'draft': 'draft', 'approve': 'approved', 'reject': 'cancel'}[self.decision]
        contacts = self.partner_ids.filtered(lambda partner: partner.state != target_state).with_context(clean_context(self.env.context))

        if self.decision == 'approve':
            contacts.partner_approve()
            message = _("%(count)s contact(s) approved.", count=len(contacts))
        elif self.decision == 'reject':
            contacts.partner_cancel()
            message = _("%(count)s contact(s) rejected.", count=len(contacts))
        else:
            contacts.partner_set_draft()
            message = _("%(count)s contact(s) set to draft.", count=len(contacts))

        if not contacts:
            message = _("The selected contacts are already in this status.")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Contact Approval"),
                'message': message,
                'type': 'success' if contacts else 'warning',
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }