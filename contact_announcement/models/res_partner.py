# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResPartner(models.Model):
    _inherit = 'res.partner'

    announcement_display_html = fields.Html(
        string='Announcements Banner',
        compute='_compute_announcement_display_html'
    )

    @api.depends('name') 
    def _compute_announcement_display_html(self):
        today = fields.Date.today()
        for partner in self:
            announcements = self.env['contact.announcement'].search([
                ('partner_ids', 'in', partner.id),
                ('start_date', '<=', today),
                '|', ('expiry_date', '=', False), ('expiry_date', '>=', today)
            ])

            if not announcements:
                partner.announcement_display_html = False
                continue

            html_content = ""
            for ann in announcements:
                bg_class = "bg-info"
                if ann.priority == 'important':
                    bg_class = "bg-danger"
                elif ann.priority == 'warning':
                    bg_class = "bg-warning text-dark"

                html_content += f"""
                    <div class="alert {bg_class} text-center mb-1 p-2" style="border-radius: 5px;">
                        <i class="fa fa-bullhorn mr-2"></i>
                        <strong>{ann.name}:</strong> {ann.content or ''}
                    </div>
                """
            partner.announcement_display_html = html_content