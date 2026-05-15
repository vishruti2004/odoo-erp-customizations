# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from datetime import timedelta
import logging
import re

_logger = logging.getLogger(__name__)


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

    start_date = fields.Datetime(
        string='Start Date', required=True, default=fields.Datetime.now)

    expiry_date = fields.Datetime(string='Expiry Date')

    last_sent_date = fields.Datetime(string='Last Sent On', readonly=True)

    internal_notes = fields.Text(string='Internal Notes')

    active = fields.Boolean(default=True)

    recurrency_interval = fields.Integer(string='Repeat Every', default=1)

    recurrency_unit = fields.Selection([
        ('minutes', 'Minutes'),
        ('hours',   'Hours'),
        ('days',    'Days'),
        ('weeks',   'Weeks'),
        ('months',  'Months'),
        ('years',   'Years'),
    ], string='Interval Unit', default='days')

    partner_domain = fields.Char(string='Contact Filter', default='[]')

    partner_ids = fields.Many2many(
        'res.partner',
        'contact_announcement_partner_rel',
        'announcement_id', 'partner_id',
        string='Contacts',
    )

    sent_partner_ids = fields.Many2many(
        'res.partner',
        'contact_announcement_sent_partner_rel',
        'announcement_id', 'partner_id',
        string='Already Notified Contacts',
    )

    # Track which partners have read this announcement
    read_partner_ids = fields.Many2many(
        'res.partner',
        'contact_announcement_read_rel',
        'announcement_id', 'partner_id',
        string='Read By',
    )

    company_id = fields.Many2one(
        'res.company', string='Company',
        required=True, readonly=True,
        default=lambda self: self.env.company,
    )

    is_active_announcement = fields.Boolean(
        string='Currently Active', compute='_compute_is_active')

    @api.depends('start_date', 'expiry_date')
    def _compute_is_active(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_active_announcement = (
                record.start_date <= now and
                (not record.expiry_date or record.expiry_date >= now)
            )

    @api.constrains('start_date', 'expiry_date')
    def _check_dates(self):
        for record in self:
            if record.expiry_date and record.expiry_date < record.start_date:
                raise ValidationError(
                    "Expiry Date cannot be earlier than Start Date.")

    @api.onchange('partner_domain')
    def _onchange_partner_domain(self):
        if not self.partner_domain or self.partner_domain == '[]':
            self.partner_ids = False
            return
        try:
            self.partner_ids = self.env['res.partner'].search(
                safe_eval(self.partner_domain))
        except Exception:
            self.partner_ids = False

    def _get_next_send_date(self, base_date):
        interval = self.recurrency_interval or 1
        delta_map = {
            'minutes': timedelta(minutes=interval),
            'hours':   timedelta(hours=interval),
            'days':    timedelta(days=interval),
            'weeks':   timedelta(weeks=interval),
            'months':  timedelta(days=interval * 30),
            'years':   timedelta(days=interval * 365),
        }
        return base_date + delta_map.get(
            self.recurrency_unit, timedelta(days=interval))

    def _is_due_to_send(self):
        self.ensure_one()
        now = fields.Datetime.now()

        if self.expiry_date and now > self.expiry_date:
            return False

        if not self.last_sent_date:
            return self.start_date <= now

        next_send_date = self._get_next_send_date(self.last_sent_date)

        if self.expiry_date and next_send_date > self.expiry_date:
            return False

        return now >= next_send_date

    # Cron
    def action_cron_send_notifications(self):
        now = fields.Datetime.now()

        due_announcements = self.search([
            ('start_date', '<=', now),
            ('active', '=', True),
            '|',
            ('expiry_date', '=', False),
            ('expiry_date', '>=', now),
        ])

        for announcement in due_announcements:
            if not announcement._is_due_to_send():
                continue
            announcement._send_notifications_core()

    def _send_notifications_core(self):
        email_template = self.env.ref(
            'contact_announcement.email_template_contact_announcement',
            raise_if_not_found=False,
        )

        for announcement in self:
            if not announcement.partner_ids:
                continue

            plain_content = re.sub(
                r'<[^>]+>', '', announcement.content or '').strip()

            notification_type = {
                'important': 'danger',
                'warning':   'warning',
                'info':      'info',
            }.get(announcement.priority, 'info')

            if announcement.last_sent_date:
                announcement.write({'sent_partner_ids': [(5, 0, 0)]})
                announcement.write({'read_partner_ids': [(5, 0, 0)]})

            for partner in announcement.partner_ids:

                if announcement.announcement_type == 'alert':

                    # Odoo inbox notification
                    announcement.message_notify(
                        partner_ids=partner.ids,
                        body=announcement.content or "",
                    )

                    target_users = self.env['res.users'].search([
                        ('partner_id', '=', partner.id),
                        ('active', '=', True),
                    ])

                    _logger.info(
                        "PARTNER=%s | USERS=%s | SHARE=%s",
                        partner.name,
                        target_users.ids,
                        target_users.mapped('share'),
                    )

                    for user in target_users:
                        # Real-time portal notification
                        self.env['bus.bus']._sendone(
                            f"contact_announcement_{partner.id}",
                            'contact_announcement',
                            {
                                'id':      announcement.id,
                                'title':   announcement.name,
                                'message': plain_content,
                                'type':    notification_type,
                                'sticky':  False,
                                'is_read': False,
                                'date':    fields.Datetime.now().strftime(
                                    "%d %b, %I:%M %p"),
                            }
                        )

                        # Real-time popup for internal users
                        self.env['bus.bus']._sendone(
                            user.partner_id,
                            'simple_notification',
                            {
                                'title':   announcement.name,
                                'message': plain_content,
                                'sticky':  False,
                                'warning': False,
                            }
                        )

                        _logger.info(
                            "Notification sent to: %s", user.name)

                elif (announcement.announcement_type == 'email'
                      and partner.email and email_template):
                    email_template.with_context(
                        current_partner=partner
                    ).send_mail(
                        announcement.id,
                        email_values={
                            'email_to':   partner.email,
                            'email_from': (
                                announcement.company_id.email_formatted
                                or self.env.company.email_formatted
                            ),
                        },
                        force_send=True,
                    )
                    _logger.info("Email sent to: %s", partner.email)

                if announcement.internal_notes:
                    partner.message_post(
                        body=announcement.internal_notes,
                        message_type='comment',
                        subtype_xmlid='mail.mt_note',
                    )

            announcement.write(
                {'last_sent_date': fields.Datetime.now()})