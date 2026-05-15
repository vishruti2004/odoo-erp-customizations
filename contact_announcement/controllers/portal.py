# -*- coding: utf-8 -*-
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

        notifications = request.env['portal.notification'].search(
            [
                ('partner_id', '=', partner.id),
                ('announcement_id', '!=', False)
            ],
            limit=20,
            order='create_date desc'
        )

        data = []
        for notif in notifications:
            data.append({
                'id': notif.id,
                'title': notif.title,
                'message': notif.message,
                'is_read': notif.is_read,
                'date': notif.create_date.strftime("%d %b, %I:%M %p"),
            })

        return data


    @http.route('/portal/notification/read', type='jsonrpc', auth='user')
    def portal_notification_read(self, notification_id):
        notification = request.env['portal.notification'].browse(int(notification_id))

        if notification.exists():
            notification.sudo().write({'is_read': True})
            return {'success': True}
        
        return {'success': False, 'message': 'Notification not found'}