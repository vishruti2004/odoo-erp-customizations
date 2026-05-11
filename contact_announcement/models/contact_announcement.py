# -*- coding: utf-8 -*-

from odoo import models, fields, api
import re
import logging
from odoo.exceptions import ValidationError


class ContactAnnouncement(models.Model):
    _name = 'contact.announcement'
    _description = 'Contact Announcement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, start_date desc'

    name = fields.Char(string='Title', required=True, tracking=True)

    announcement_type = fields.Selection([
        ('alert', 'Alert'),
        ('email', 'Email'),
    ], string='Type', required=True, default='alert', tracking=True)

    priority = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('important', 'Important'),
    ], string='Priority', required=True, default='info', tracking=True)

    content = fields.Html(string='Message', sanitize=True)
    start_date = fields.Date(string='Start Date', required=True, default=fields.Date.today)
    expiry_date = fields.Date(string='Expiry Date')

    recurrency_interval = fields.Integer(string='Repeat Every', default=1)
    recurrency_unit = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours', 'Hours'),
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
    ], string='Interval Unit', default='days')

    partner_ids = fields.Many2many(
        'res.partner',
        'contact_announcement_partner_rel',
        'announcement_id',
        'partner_id',
        string='Contacts',
    )

    sent_partner_ids = fields.Many2many(
        'res.partner',
        'contact_announcement_sent_partner_rel',
        'announcement_id',
        'partner_id',
        string='Already Notified Contacts',
    )

    internal_notes = fields.Text(string='Internal Notes')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    is_active_announcement = fields.Boolean(
        string='Currently Active',
        compute='_compute_is_active',
        store=False,
    )

    @api.depends('start_date', 'expiry_date')
    def _compute_is_active(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_active_announcement = (
                rec.start_date <= today and
                (not rec.expiry_date or rec.expiry_date >= today)
            )

    @api.constrains('start_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.expiry_date and rec.expiry_date < rec.start_date:
                raise ValidationError("Expiry Date cannot be earlier than Start Date.")

    def _strip_html(self, html_content):
        """HTML Tags kadhva mate jethi Popup ma message sakhro dekhay"""
        if not html_content:
            return ''
        clean = re.sub(r'<[^>]+>', ' ', html_content)
        return re.sub(r'\s+', ' ', clean).strip()

    def action_cron_send_notifications(self):
        """Automated Cron Call"""
        today = fields.Date.today()
        announcements = self.search([
            ('start_date', '<=', today),
            ('active', '=', True),
            '|',
            ('expiry_date', '=', False),
            ('expiry_date', '>=', today),
        ])
        announcements._send_notifications_core()

    def action_send_notifications(self):
        """Manual Button Call"""
        self._send_notifications_core()

    def _send_notifications_core(self):
        """Final Logic: Inbox Notification + Real-time Popup"""
        template = self.env.ref('contact_announcement.email_template_contact_announcement', raise_if_not_found=False)
        
        for ann in self:
            pending = ann.partner_ids - ann.sent_partner_ids
            if not pending:
                continue

            notif_type = {'important': 'danger', 'warning': 'warning', 'info': 'info'}.get(ann.priority, 'info')
            plain_content = ann._strip_html(ann.content)

            for partner in pending:
                if ann.announcement_type == 'alert':
                    ann.sudo().message_post(
                        body=ann.content or "", # Direct content vapro, HTML Odoo handle kari leshe
                        subject=ann.name,
                        partner_ids=partner.ids,
                        message_type='notification', # Proper Notification layout mate
                        subtype_xmlid='mail.mt_comment',
                        author_id=ann.company_id.partner_id.id,
                    )

                    partner_users = self.env['res.users'].sudo().search([
                        ('partner_id', '=', partner.id),
                        ('active', '=', True),
                    ])
                    for user in partner_users:
                        # self.env['bus.bus']._sendone(
                        #     user.partner_id,
                        #     'simple_notification',
                        #     {
                        #         'title': ann.name,
                        #         'message': plain_content,
                        #         'sticky': ann.priority == 'important',
                        #         'type': notif_type,
                        #     }
                        # )

                        user._bus_send(
                            "simple_notification",
                            {
                                "title": ann.name,
                                "message": plain_content,
                                "sticky": ann.priority == 'important',
                                "type": notif_type,
                            }
                        )

                # EMAIL --
                elif ann.announcement_type == 'email' and partner.email and template:
                    template.with_context(current_partner=partner).send_mail(
                        ann.id,
                        email_values={
                            'email_to': partner.email,
                            'email_from': ann.company_id.email_formatted or self.env.company.email_formatted,
                        },
                        force_send=True,
                    )

                ann.sudo().write({'sent_partner_ids': [(4, partner.id)]})