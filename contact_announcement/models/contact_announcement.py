# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval
from datetime import timedelta
import logging
import re

_logger = logging.getLogger(__name__)


class ContactAnnouncement(models.Model):
    # Database table nu naam
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

    start_date = fields.Datetime(string='Start Date', required=True, default=fields.Datetime.now)

    expiry_date = fields.Datetime(string='Expiry Date')

  
    last_sent_date = fields.Datetime(string='Last Sent On', readonly=True)

    recurrency_interval = fields.Integer(string='Repeat Every', default=1)

    recurrency_unit = fields.Selection([
        ('minutes', 'Minutes'), ('hours', 'Hours'), ('days', 'Days'),
        ('weeks', 'Weeks'), ('months', 'Months'), ('years', 'Years'),
    ], string='Interval Unit', default='days')

   
    partner_domain = fields.Char(string='Contact Filter', default='[]')

  
    partner_ids = fields.Many2many(
        'res.partner', 'contact_announcement_partner_rel',
        'announcement_id', 'partner_id', string='Contacts',
    )

    sent_partner_ids = fields.Many2many(
        'res.partner', 'contact_announcement_sent_partner_rel',
        'announcement_id', 'partner_id', string='Already Notified Contacts',
    )

    internal_notes = fields.Text(string='Internal Notes')

    company_id = fields.Many2one(
        'res.company', string='Company',
        required=True, readonly=True,
        default=lambda self: self.env.company,
    )

    active = fields.Boolean(default=True)

    is_active_announcement = fields.Boolean(
        string='Currently Active', compute='_compute_is_active',
    )


    @api.depends('start_date', 'expiry_date')
    def _compute_is_active(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_active_announcement = (
                rec.start_date <= now and
                (not rec.expiry_date or rec.expiry_date >= now)
            )


    @api.constrains('start_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            #  expiry date set chhe ane start date thi pehla chhe to error
            if rec.expiry_date and rec.expiry_date < rec.start_date:
                raise ValidationError("Expiry Date cannot be earlier than Start Date.")


    @api.onchange('partner_domain')
    def _onchange_partner_domain(self):
        if not self.partner_domain or self.partner_domain == '[]':
            self.partner_ids = False
            return
        try:
            self.partner_ids = self.env['res.partner'].search(safe_eval(self.partner_domain))
        except Exception:
            self.partner_ids = False


    def _get_next_send_date(self, base_date):
        # Base date (last_sent_date) + interval = next send date calculate karo
        interval = self.recurrency_interval or 1

        delta = {
            'minutes': timedelta(minutes=interval),  
            'hours':   timedelta(hours=interval),     
            'days':    timedelta(days=interval),     
            'weeks':   timedelta(weeks=interval),     
            'months':  timedelta(days=interval * 30), 
            'years':   timedelta(days=interval * 365),
        }.get(self.recurrency_unit, timedelta(days=interval))

        return base_date + delta

    def _is_due_to_send(self):
        # Aa announcement hve send karvi joie ke nahi te check karo
        self.ensure_one()  
        now = fields.Datetime.now()

        # Jо expiry date pass thai gayi chhe to send na kare
        if self.expiry_date and now > self.expiry_date:
            return False

        # Pehli vaar send — last_sent_date nathi, to start_date aavi gayi chhe ke check karo
        if not self.last_sent_date:
            return self.start_date <= now

        # Next send date calculate karo last_sent_date thi
        next_send = self._get_next_send_date(self.last_sent_date)

        # Jо next send date expiry cross kare to send na karo
        #  next_send = 12 June, expiry = 20 May → False
        if self.expiry_date and next_send > self.expiry_date:
            return False

        # Hava ni time next_send thi moti ya barabar chhe? → Send karo
        return now >= next_send


    def action_cron_send_notifications(self):
        now = fields.Datetime.now()

        # Aaje active hoy evu j announcements fetch karo
        announcements = self.search([
            ('start_date', '<=', now),    
            ('active', '=', True),           
            '|',                             
            ('expiry_date', '=', False),    
            ('expiry_date', '>=', now),      
        ])


        for ann in announcements:
            # Check karo ke aa announcement hve send karvi joie ke nahi
            if not ann._is_due_to_send():
                continue 

            # Due chhe to send karo
            ann._send_notifications_core()

    def _send_notifications_core(self):
        # Actual send logic — Alert ya Email mokle chhe

        template = self.env.ref(
            'contact_announcement.email_template_contact_announcement',
            raise_if_not_found=False,  
        )

        for ann in self:
            # Koi partner set nathi to skip karo
            if not ann.partner_ids:
                continue

            plain_content = ann._strip_html(ann.content)
            notif_type = {'important': 'danger', 'warning': 'warning', 'info': 'info'}.get(ann.priority, 'info')

            # Repeat cycle — last_sent_date chhe matlab pehla send thai gayu chhe
            # sent_partner_ids clear karo jethi badha partners fari receive kare
            if ann.last_sent_date:
                ann.sudo().write({'sent_partner_ids': [(5, 0, 0)]})  

            # Already sent contacts - karo — sirf pending j process karo
            pending = ann.partner_ids - ann.sent_partner_ids

            for partner in pending:

                if ann.announcement_type == 'alert':

                    #  inbox ma notification send kare
                    ann.sudo().message_notify(
                        partner_ids=partner.ids,       
                        body=ann.content or "",       
                        # author_id=ann.company_id.partner_id.id,  
                    )

                    # Real-time browser popup mokle
                    users = self.env['res.users'].sudo().search([
                        ('partner_id', '=', partner.id),  
                        ('active', '=', True),          
                    ])
                    for user in users:
                        # WebSocket thi real-time notification moklo
                        user._bus_send("simple_notification", {
                            "title":   ann.name,                       
                            "message": plain_content,                   
                            "type":    notif_type,                     
                        })
                        _logger.info("Bus sent to: %s", user.name)

                elif ann.announcement_type == 'email' and partner.email and template:
                    template.with_context(current_partner=partner).send_mail(
                        ann.id,
                        email_values={
                            'email_to':   partner.email,   
                            'email_from': ann.company_id.email_formatted or self.env.company.email_formatted,
                        },
                        force_send=True, 
                    )
                    _logger.info("Email sent to: %s", partner.email)

                # Send thaya pachhi aa partner ne sent list ma add karo
                # (4, partner.id) = add this record
                ann.sudo().write({'sent_partner_ids': [(4, partner.id)]})

                # Internal notes set chhe to partner na chatter ma add karo
                if ann.internal_notes:
                    partner.message_post(
                        body=ann.internal_notes,      
                        message_type='comment',           
                        subtype_xmlid='mail.mt_note',     
                    )

            # Badha partners process thaya — last_sent_date update kare
            # Next cycle aa date thi calculate thashe
            ann.sudo().write({'last_sent_date': fields.Datetime.now()})

    def _strip_html(self, html_content):
        if not html_content:
            return ''
        return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html_content)).strip()