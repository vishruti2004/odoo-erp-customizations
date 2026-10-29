# -*- coding: utf-8 -*-

from odoo import api, models
from odoo.fields import Domain

class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model
    def _message_fetch(self, domain, *, advanced_domain=None, **kwargs):
        advanced = self._advanced_chatter_domain(advanced_domain, kwargs.get("thread"))
        if advanced is None:
            return super()._message_fetch(domain, **kwargs)
        domain = Domain(True if domain is None else domain) & advanced
        res = super()._message_fetch(domain, **kwargs)
        if "count" not in res:
            if "limit" in kwargs and kwargs["limit"] is None:
                res["count"] = len(res["messages"])
            else:
                unlimited = dict(kwargs, limit=None, before=None, after=None, around=None)
                res["count"] = len(super()._message_fetch(domain, **unlimited)["messages"])
        return res

    @api.model
    def _advanced_chatter_domain(self, advanced_domain, thread):
        if (
            not advanced_domain
            or self.env.su
            or thread is None
            or not hasattr(thread, "_advanced_chatter_message_domain_rules")
            or not self.env.user.has_group("advanced_chatter.group_advanced_chatter_user")
        ):
            return None
        rules = thread._advanced_chatter_message_domain_rules()
        conditions = []
        for condition in advanced_domain:
            if not isinstance(condition, (list, tuple)) or len(condition) != 3:
                return None
            fname, operator, value = condition
            if operator not in rules.get(fname, ()):
                return None
            conditions.append(Domain(fname, operator, value))
        return Domain.AND(conditions)
