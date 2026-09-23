# -*- coding: utf-8 -*-

from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model
    def _message_fetch(self,domain,*,thread=None,search_term=None,is_notification=None,before=None,after=None,around=None,limit=30,date_from=None,date_to=None,author_id=None,message_type=None,res_model_filter=None,res_id_filter=None,**kwargs):
       
        domain = domain or []
        extra_domain = []

        if date_from:
            extra_domain.append(('date', '>=', date_from))
        if date_to:
            extra_domain.append(('date', '<=', date_to))
        if author_id:
            extra_domain.append(('author_id', '=', author_id))
        if message_type:
            extra_domain.append(('message_type', '=', message_type))
        if res_model_filter:
            extra_domain.append(('model', '=', res_model_filter))
        if res_id_filter:
            extra_domain.append(('res_id', '=', res_id_filter))

        domain = domain + extra_domain

        return super()._message_fetch(domain,thread=thread,search_term=search_term,is_notification=is_notification,before=before,after=after,around=around,limit=limit,**kwargs)