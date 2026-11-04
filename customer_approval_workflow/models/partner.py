from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.fields import Domain


class PartnerView(models.Model):
    _inherit = 'res.partner'
    _description = "Customer Approval View"

    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('cancel', 'Rejected'),
    ], required=True, default='draft', tracking=True, string='Status', readonly=True)

    approved_by = fields.Many2one(
        'res.users', string='Approved By', copy=False)

    @api.model
    def name_search(self, name='', domain=None, operator='ilike', limit=100):
        domain = Domain(domain or Domain.TRUE) & Domain('state', '=', 'approved')
        return super().name_search(name, domain, operator, limit)

    def _check_contact_manager(self):
        if not self.env.user.has_group('customer_approval_workflow.group_contact_manager'):
            raise AccessError(_("Only Contact Managers can change the contact status."))

    def partner_approve(self):
        self._check_contact_manager()
        for record in self:
            record.sudo().write({
                'state': 'approved',
                'approved_by': self.env.user.id
            })

    def action_open_approval_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _("Approve/Reject Contacts"),
            'res_model': 'contact.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_partner_ids': self.ids},
        }

    def partner_set_draft(self):
        self._check_contact_manager()
        self.sudo().write({'state': 'draft'})

    def partner_cancel(self):
        self._check_contact_manager()
        self.sudo().write({'state': 'cancel'})

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == 'form':
            for node in arch.iter('field'):
                readonly = (node.get('readonly') or '').strip()
                if node.get('name') in ('state', 'approved_by') or readonly.lower() in ('1', 'true'):
                    continue
                node.set('readonly', f"({readonly}) or (state == 'approved')" if readonly else "state == 'approved'")
        return arch, view

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._send_approval_request()
        return records

    def _send_approval_request(self):
        template = self.env.ref(
            'customer_approval_workflow.customer_approval_email_template_ip', raise_if_not_found=False)
        if not template:
            return
        manager_group = self.env.ref(
            'customer_approval_workflow.group_contact_manager')
        for record in self:
            company = record.company_id or self.env.company
            managers = self.env['res.users'].sudo().search([
                ('group_ids', 'in', manager_group.id),
                ('company_ids', 'in', company.id),
                ('id', '!=', self.env.user.id),
            ])
            partner_ids = managers.mapped('partner_id').ids
            if not partner_ids:
                continue
            template.sudo().with_company(company).send_mail(
                record.id,
                force_send=True,
                email_values={
                    'email_to': False,
                    'recipient_ids': [(6, 0, partner_ids)],
                }
            )