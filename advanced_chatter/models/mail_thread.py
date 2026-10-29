# -*- coding: utf-8 -*-

import logging
import re
from html import escape
from odoo import api, models
from odoo.fields import Domain
from odoo.tools import format_date, format_datetime
from odoo.tools.mail import html_to_inner_content
_logger = logging.getLogger(__name__)

class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    _advanced_chatter_message_filter_fields = ("author_id", "message_type", "subtype_id")
    _advanced_chatter_message_search_fields = (
        "author_id",
        "email_from",
        "subtype_id",
        "message_type",
        "subject",
    )
    _advanced_chatter_activity_filter_fields = ("user_id", "activity_type_id", "state")
    _advanced_chatter_activity_search_fields = (
        "activity_type_id",
        "summary",
        "user_id",
        "date_deadline",
        "state",
    )
    _advanced_chatter_date_fields = {"mail.message": "date", "mail.activity": "date_deadline"}
    _advanced_chatter_export_fields = (
        ("id", "id"),
        ("create_date", "create_date"),
        ("create_uid", "create_uid"),
        ("write_date", "write_date"),
        ("write_uid", "write_uid"),
        ("date", "date_deadline"),
        ("author_id", "user_id"),
        ("message_type", "activity_type_id"),
        ("subject", "summary"),
        ("body", "note"),
    )

    @api.readonly
    def get_advanced_chatter_filter_options(self, is_notification=None):
        thread = self._advanced_chatter_thread()
        if not thread:
            return {}
        return {
            "message": thread._advanced_chatter_filter_section(
                thread._advanced_chatter_messages(is_notification=is_notification),
                self._advanced_chatter_message_filter_fields,
            ),
            "activity": thread._advanced_chatter_filter_section(
                thread._advanced_chatter_activities(),
                self._advanced_chatter_activity_filter_fields,
            ),
        }

    @api.readonly
    def get_advanced_chatter_suggestions(self, search_term, is_notification=None):
        thread = self._advanced_chatter_thread()
        term = (search_term or "").strip().casefold()
        if not thread or not term:
            return []
        pattern = re.compile(r"(?:^|[\W_])" + re.escape(term))
        messages = thread._advanced_chatter_messages(is_notification=is_notification)
        groups = [
            *thread._advanced_chatter_record_groups(
                messages, self._advanced_chatter_message_search_fields, "message", term, pattern
            ),
            *thread._advanced_chatter_record_groups(
                thread._advanced_chatter_activities(),
                self._advanced_chatter_activity_search_fields,
                "activity",
                term,
                pattern,
            ),
            *thread._advanced_chatter_mention_groups(messages, term, pattern),
        ]
        return sorted(groups, key=lambda group: group["field_match"])

    def _advanced_chatter_thread(self):
        self.ensure_one()
        if not self.env.user.has_group("advanced_chatter.group_advanced_chatter_user"):
            return self.browse()
        thread = self._get_thread_with_access(self.id, mode="read")
        if not thread or not thread.has_access("read"):
            return self.browse()
        return thread

    def _advanced_chatter_messages(self, search_term=None, is_notification=None, advanced_domain=None):
        return self.env["mail.message"]._message_fetch(
            Domain.TRUE,
            thread=self,
            search_term=search_term,
            is_notification=is_notification,
            advanced_domain=advanced_domain,
            limit=None,
        )["messages"]

    def _advanced_chatter_message_domain_rules(self):
        rules = {fname: ("=",) for fname in self._advanced_chatter_message_filter_fields}
        rules.update({fname: ("=",) for fname in self._advanced_chatter_message_search_fields})
        rules[self._advanced_chatter_date_fields["mail.message"]] = (">=", "<=")
        rules["body"] = ("ilike",)
        return rules

    def _advanced_chatter_activities(self):
        if "activity_ids" in self._fields:
            return self.activity_ids
        return self.env["mail.activity"]

    def _advanced_chatter_label(self, record, fname):
        field = record._fields[fname]
        value = record[fname]
        if not value:
            return ""
        if field.type == "date":
            return format_date(self.env, value)
        if field.type == "datetime":
            return format_datetime(self.env, value)
        if field.type == "html":
            return html_to_inner_content(value)
        if field.type == "many2one":
            return value.display_name if value.has_access("read") else ""
        return str(field.convert_to_export(value, record))

    def _advanced_chatter_values(self, records, fname):
        field = records._fields[fname]
        values = {}
        for record in records:
            value = record[fname]
            if not value:
                continue
            key = value.id if field.type == "many2one" else str(value)
            if key not in values:
                label = self._advanced_chatter_label(record, fname)
                if not label:
                    continue
                if field.type in ("date", "datetime"):
                    value = field.to_string(value)
                elif field.type == "many2one":
                    value = value.id
                values[key] = {"label": label, "value": value, "ids": []}
            values[key]["ids"].append(record.id)
        return list(values.values())

    def _advanced_chatter_filter_section(self, records, fnames):
        date_fname = self._advanced_chatter_date_fields[records._name]
        fields_info = records.fields_get([*fnames, date_fname], ["string", "type"])
        groups = []
        for fname in fnames:
            options = [
                {"value": value["value"], "label": value["label"]}
                for value in self._advanced_chatter_values(records, fname)
            ]
            groups.append({
                "field": fname,
                "label": fields_info[fname]["string"],
                "type": fields_info[fname]["type"],
                "options": sorted(options, key=lambda option: option["label"].casefold()),
            })
        return {
            "groups": groups,
            "date_field": {"name": date_fname, "label": fields_info[date_fname]["string"]},
        }

    @api.model
    def _advanced_chatter_matches(self, label, term, pattern):
        text = label.casefold()
        return text == term or bool(pattern.search(text))

    @api.model
    def _advanced_chatter_rank(self, label, term):
        text = label.casefold()
        return 0 if text == term else 1 if text.startswith(term) else 2

    def _advanced_chatter_group(self, key, label, kind, items, term, pattern):
        field_match = label.casefold() == term
        if not field_match:
            items = [item for item in items if self._advanced_chatter_matches(item["label"], term, pattern)]
            items.sort(key=lambda item: self._advanced_chatter_rank(item["label"], term))
        else:
            items.sort(key=lambda item: item["label"].casefold())
        if not items:
            return None
        return {"key": key, "label": label, "kind": kind, "items": items, "field_match": field_match}

    def _advanced_chatter_record_groups(self, records, fnames, kind, term, pattern):
        fields_info = records.fields_get(list(fnames), ["string"])
        groups = []
        for fname in fnames:
            items = []
            for value in self._advanced_chatter_values(records, fname):
                item = {"label": value["label"]}
                if kind == "activity":
                    item["activity_ids"] = value["ids"]
                else:
                    item["domain"] = [[fname, "=", value["value"]]]
                items.append(item)
            group = self._advanced_chatter_group(
                f"{records._name}:{fname}", fields_info[fname]["string"], kind, items, term, pattern
            )
            if group:
                groups.append(group)
        return groups

    def _advanced_chatter_mention_groups(self, messages, term, pattern):
        texts = "\n".join(html_to_inner_content(message.body) for message in messages).casefold()
        if term not in texts:
            return []
        mixin_fields = set()
        for mixin in ("mail.thread", "mail.activity.mixin"):
            if mixin in self.env:
                mixin_fields.update(self.env[mixin]._fields)
        fields_info = self.fields_get(attributes=["string"])

        def mention(label):
            return {"label": label, "domain": [["body", "ilike", escape(label, quote=False)]]}

        groups = []
        comodels = []
        for fname, field in self._fields.items():
            if fname in mixin_fields or fname not in fields_info:
                continue
            if field.type == "selection":
                items = [
                    mention(label)
                    for _value, label in field._description_selection(self.env)
                    if label and label.casefold() in texts
                ]
                group = self._advanced_chatter_group(
                    f"{self._name}:{fname}", fields_info[fname]["string"], "message", items, term, pattern
                )
                if group:
                    groups.append(group)
            elif field.relational and field.comodel_name not in comodels:
                comodels.append(field.comodel_name)

        for comodel in comodels:
            Comodel = self.env[comodel]
            if Comodel._abstract or Comodel._transient or not Comodel.has_access("read"):
                continue
            try:
                with self.env.cr.savepoint():
                    names = Comodel.name_search(term)
            except Exception: 
                _logger.debug("Advanced chatter: name_search failed on %s", comodel, exc_info=True)
                continue
            items = [mention(name) for _id, name in names if name and name.casefold() in texts]
            group = self._advanced_chatter_group(
                f"mention:{comodel}", self.env["ir.model"]._get(comodel).name, "message", items, term, pattern
            )
            if group:
                groups.append(group)
        return groups

    def _get_advanced_chatter_export(self, messages_params=None, activity_ids=None):
        thread = self._advanced_chatter_thread()
        Message = self.env["mail.message"]
        Activity = self.env["mail.activity"]
        messages = Message
        activities = Activity
        if thread and messages_params is not None:
            messages = thread._advanced_chatter_messages(**messages_params)
        if thread and activity_ids is not None:
            activities = thread._advanced_chatter_activities().filtered(
                lambda activity: activity.id in activity_ids
            )

        message_fnames = [message_fname for message_fname, _activity_fname in self._advanced_chatter_export_fields]
        activity_fnames = [activity_fname for _message_fname, activity_fname in self._advanced_chatter_export_fields]
        message_info = Message.fields_get(message_fnames, ["string"])
        activity_info = Activity.fields_get(activity_fnames, ["string"])
        headers = []
        for message_fname, activity_fname in self._advanced_chatter_export_fields:
            message_label = message_info[message_fname]["string"]
            activity_label = activity_info[activity_fname]["string"]
            headers.append(
                message_label if message_label == activity_label else f"{message_label} / {activity_label}"
            )
        headers.append(self.env._("Result Type"))

        IrModel = self.env["ir.model"]
        rows = [
            [self._advanced_chatter_label(message, fname) for fname in message_fnames]
            + [IrModel._get(Message._name).name]
            for message in messages
        ]
        rows += [
            [self._advanced_chatter_label(activity, fname) for fname in activity_fnames]
            + [IrModel._get(Activity._name).name]
            for activity in activities
        ]
        return headers, rows
