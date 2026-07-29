# -*- coding: utf-8 -*-
import re
from odoo import http
from odoo.http import request

class PortalAnnouncement(http.Controller):

    @http.route('/my/home', type='http', auth='user', website=True)
    def portal_my_home(self, **kw):
        partner = request.env.user.partner_id
        
        announcements = request.env['contact.announcement'].search([
            ('partner_ids', 'in', partner.id), 
            ('active', '=', True),
        ])

        values = {
            'announcements': announcements,
        }
        return request.render('portal.portal_my_home', values)

    @http.route('/portal/notifications', type='jsonrpc', auth='user')
    def portal_notifications(self):
        partner = request.env.user.partner_id

        announcements = request.env['contact.announcement'].search([
            ('partner_ids', 'in', partner.id),
            ('active', '=', True)
        ], limit=20, order='last_sent_date desc')

        data = []
        for ann in announcements:
            is_read = partner.id in ann.read_partner_ids.ids
            
            plain_message = re.sub(r'<[^>]+>', '', ann.content).strip() if ann.content else ''

            data.append({
                'id': ann.id,
                'title': ann.name,
                'message': plain_message,
                'is_read': is_read,
                'date': ann.last_sent_date.strftime("%d %b, %I:%M %p") if ann.last_sent_date else '',
            })

        return data

    @http.route('/portal/notification/read', type='jsonrpc', auth='user')
    def portal_notification_read(self, notification_id):
        partner = request.env.user.partner_id
        announcement = request.env['contact.announcement'].browse(int(notification_id))

        if announcement.exists():
            announcement.sudo().write({
                'read_partner_ids': [(4, partner.id)]
            })
            return {'success': True}
        
        return {'success': False, 'message': 'Notification not found'}