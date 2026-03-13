from odoo.addons.account.controllers.portal import PortalAccount
from odoo.http import request
from odoo.fields import Domain


class PortalAccountInherit(PortalAccount):

    def _get_invoices_domain(self, m_type=None):

        # Original Odoo domain
        domain = super()._get_invoices_domain(m_type)

        user = request.env.user

        # Admin → show all invoices
        if user.has_group('base.group_system'):
            return domain

        # Find doctor linked with current user
        doctor = request.env['hospital.doctor'].search([
            ('user_id', '=', user.id)
        ], limit=1)

        # Find patient linked with current user
        patient = request.env['hospital.patient'].search([
            ('partner_id', '=', user.partner_id.id)
        ], limit=1)

        partner_ids = []

        if patient:
            partner_ids.append(patient.partner_id.id)

    
        if doctor:

            appointments = request.env['hospital.appointment'].search([
                ('doctor_id', '=', doctor.id)
            ])

            patient_partners = appointments.mapped('patient_id.partner_id')

            partner_ids += patient_partners.ids

        # Remove duplicate partner ids
        partner_ids = list(set(partner_ids))

        # Apply invoice filter
        if partner_ids:
            domain &= Domain('partner_id', 'in', partner_ids)

        return domain