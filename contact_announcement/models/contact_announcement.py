# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ContactAnnouncement(models.Model):
    _name = 'contact.announcement'
    _description = 'Contact Announcement'

    name = fields.Char(string='Title', required=True)

    announcement_type = fields.Selection([
        ('alert', 'Alert'),
        ('email', 'Email'),
    ], string='Type', required=True, default='alert')

    priority = fields.Selection([
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('important', 'Important'),
    ], string='Priority', required=True, default='info')

    recurrency_interval = fields.Integer(
    string='Repeat Every',
    default=1,
    )

    recurrency_unit = fields.Selection(
        selection=[
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
        ],
        string='Interval Unit',
        default='days',
    )

    content = fields.Html(string='Message', sanitize=True)
    start_date = fields.Datetime(string='Start Date', required=True, default=fields.Date.today) 
    expiry_date = fields.Datetime(string='Expiry Date') 

    partner_ids = fields.Many2many('res.partner', string='Contacts')

    internal_notes = fields.Text(string='Internal Notes')

    @api.constrains('start_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.expiry_date and rec.start_date and rec.expiry_date < rec.start_date:
                raise ValidationError("Expiry Date cannot be earlier than Start Date.")

    # Partner banner recompute
    def _recompute_partner_banners(self):
        partners = self.mapped('partner_ids')
        if partners:
            partners.invalidate_recordset(['announcement_display_html'])

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._recompute_partner_banners()
        return records

    def write(self, vals):
        result = super().write(vals)
        self._recompute_partner_banners()
        return result