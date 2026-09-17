# -*- coding: utf-8 -*-

from odoo import api, models


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model
    def _message_fetch(
        self,
        domain,
        *,
        thread=None,
        search_term=None,
        is_notification=None,
        before=None,
        after=None,
        around=None,
        limit=30,
        # --- Advanced Chatter Search additions ---
        date_from=None,
        date_to=None,
        author_id=None,
        message_type=None,
        res_model_filter=None,
        res_id_filter=None,
        **kwargs
    ):
        """Override of mail.message._message_fetch (Odoo 19.0 signature).

        Odoo's own /mail/thread/messages controller forwards its whole
        `fetch_params` dict straight into this method as **kwargs, so the
        extra keys below reach us automatically as soon as the frontend
        sends them - no controller override needed for 19.0.

        All original Odoo functionality is preserved: we only ever ADD
        extra AND-ed conditions on top of the incoming `domain`, then
        delegate everything else (keyword search, thread scoping,
        is_notification, pagination) to super()._message_fetch().
        """
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

        return super()._message_fetch(
            domain,
            thread=thread,
            search_term=search_term,
            is_notification=is_notification,
            before=before,
            after=after,
            around=around,
            limit=limit,
            **kwargs
        )