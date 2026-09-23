/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { Thread } from "@mail/core/common/thread";
import { SearchMessageInput } from "@mail/core/common/search_message_input";
import { useService } from "@web/core/utils/hooks";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { onWillDestroy, onWillStart, useEffect, useState } from "@odoo/owl";
import { FormCompiler } from "@web/views/form/form_compiler";
import { setAttributes } from "@web/core/utils/xml";
import { evaluateExpr } from "@web/core/py_js/py";

const LOG = "[AdvancedChatter]";
const log = (...args) => console.log(LOG, ...args);

function createEmptyFilters() {
    return {
        keyword: "",
        activeKeyword: "",
        activeKeywordMode: "",
        dateFrom: "",
        dateTo: "",
        userId: "",
        messageType: "",
        subtypeId: "",
        activityTypeId: "",
        activityUserId: "",
        activityState: "",
        fieldName: "",
        fieldLabel: "",
        fieldValue: "",
        fieldValueLabel: "",
    };
}

function clearFieldSelection(filters) {
    filters.fieldName = "";
    filters.fieldLabel = "";
    filters.fieldValue = "";
    filters.fieldValueLabel = "";
}

Chatter.props.push("advancesearch?", "advancefilter?");

patch(Chatter.prototype, {
    get childSubEnv() {
        return { ...super.childSubEnv, advancedChatterSearch: this };
    },

    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.hasAdvancedChatterAccess = false;
        this.showAdvancedSearch = this.props.advancesearch !== false;
        this.showAdvancedFilters = this.props.advancefilter !== false;

        this._filterChangeListeners = new Set();

        this.searchableFields = {};
        this.suggestions = [];

        this.fieldValueMessageIds = new Map();
        this.messageTypeOptions = [];
        this.activityStateOptions = [];
        this.resModel = null;
        this.resId = null;
        this._extractedSignature = null;

        this.advancedFilterState = useState({
            showSuggestions: false,
            expandedSuggestionGroup: null,
            filters: createEmptyFilters(),
            subtypes: [],
            activityTypes: [],
        });

        onWillStart(async () => {
            this.resModel = this.props.resModel || this.props.record?.resModel || this.state.thread?.model;
            this.resId = this.props.resId || this.props.record?.resId || this.state.thread?.id;
            log("init", this.resModel, this.resId);

            this.hasAdvancedChatterAccess = await this.orm.call(
                "res.users", "check_advanced_chatter_access", []
            );
            if (!this.hasAdvancedChatterAccess) return;

            try {
                const m = await this.orm.call("mail.message", "fields_get", [["message_type"]]);
                this.messageTypeOptions = (m.message_type?.selection || [])
                    .map(([value, label]) => ({ value, label }));
            } catch (e) { console.error(LOG, e); }

            try {
                const a = await this.orm.call("mail.activity", "fields_get", [["state"]]);
                this.activityStateOptions = (a.state?.selection || [])
                    .map(([value, label]) => ({ value, label }));
            } catch (e) { console.error(LOG, e); }

            try {
                this.advancedFilterState.subtypes = await this.orm.searchRead(
                    "mail.message.subtype", [], ["id", "name"],
                    { limit: 200, order: "name asc" });
            } catch (e) { console.error(LOG, e); }

            try {
                this.advancedFilterState.activityTypes = await this.orm.searchRead(
                    "mail.activity.type", [], ["id", "name"],
                    { limit: 200, order: "name asc" });
            } catch (e) { console.error(LOG, e); }

            await this.loadAllFields();
        });

        useEffect(
            () => {
                const count = this.threadMessages.length;
                const sig = `${this.resId}|${count}`;
                if (count > 0 && this._extractedSignature !== sig) {
                    log(`thread messages ready (${count}) — extracting...`);
                    this.extractAllSuggestions().then(() => {
                        this._extractedSignature = sig;
                        this.notifyFiltersChanged(false);
                    });
                }
            },
            () => [this.threadMessages.length, this.resId]
        );
    },

    async loadAllFields() {
        const result = {};
        const USEFUL_TYPES = new Set([
            "char", "text", "many2one", "selection", "integer", "float",
            "monetary", "date", "datetime", "html",
            "one2many", "many2many",
        ]);
        const EXCLUDED_FIELDS = new Set([
            "id", "create_uid", "create_date", "write_uid", "write_date",
            "__last_update", "display_name", "access_token", "message_ids",
        ]);

        try {
            const messageFields = await this.orm.call("mail.message", "fields_get",
                [[], ["string", "type", "relation", "selection"]]);
            const KEPT_MESSAGE_FIELDS = ["author_id", "subtype_id", "message_type", "subject", "email_from"];
            for (const [name, def] of Object.entries(messageFields || {})) {
                if (!KEPT_MESSAGE_FIELDS.includes(name)) continue;
                result[name] = {
                    name, string: def.string, type: def.type,
                    relation: def.relation, selection: def.selection,
                    source: "message",
                };
            }
        } catch (e) { console.error(LOG, e); }

        if (this.resModel) {
            try {
                const recordFields = await this.orm.call(this.resModel, "fields_get",
                    [[], ["string", "type", "relation", "selection", "searchable"]]);
                for (const [name, def] of Object.entries(recordFields || {})) {
                    if (EXCLUDED_FIELDS.has(name)) continue;
                    if (!USEFUL_TYPES.has(def.type)) continue;
                    if (def.searchable === false) continue;
                    if (result[name]) continue;
                    result[name] = {
                        name, string: def.string, type: def.type,
                        relation: def.relation, selection: def.selection,
                        source: "record",
                    };
                }
            } catch (e) { console.error(LOG, e); }
        }

        this.searchableFields = result;
        log("loaded fields:", Object.keys(result).length);
    },


    async extractAllSuggestions() {
        const suggestions = [];
        const seen = new Set();
        const fieldValueMessageIds = new Map();

        const add = (fieldName, displayName, rawValue, messageId = null) => {
            if (!displayName) return;
            const label = String(displayName).trim();
            if (!label || label === "false" || label === "undefined") return;
            const key = `${fieldName}|${label.toLowerCase()}`;

            if (!seen.has(key)) {
                seen.add(key);
                const field = this.searchableFields[fieldName];
                suggestions.push({
                    fieldName,
                    fieldLabel: field?.string || fieldName,
                    fieldType: field?.type || "",
                    displayName: label,
                    rawValue,
                });
            }

            if (messageId !== null && messageId !== undefined) {
                const id = Number(messageId);
                if (Number.isFinite(id)) {
                    if (!fieldValueMessageIds.has(key)) {
                        fieldValueMessageIds.set(key, new Set());
                    }
                    fieldValueMessageIds.get(key).add(id);
                }
            }
        };

        const messages = this.threadMessages;
        const messageTypeLabels = new Map(this.messageTypeOptions.map((t) => [t.value, t.label]));
        for (const msg of messages) {
            const msgId = msg.id;
            if (msg.author?.id && msg.author?.name) add("author_id", msg.author.name, msg.author.id, msgId);
            if (msg.email_from && typeof msg.email_from === "string") add("email_from", msg.email_from, msg.email_from, msgId);
            if (msg.subtype_id?.id && msg.subtype_id?.name) add("subtype_id", msg.subtype_id.name, msg.subtype_id.id, msgId);
            if (msg.message_type) {
                const label = messageTypeLabels.get(msg.message_type) || msg.message_type;
                add("message_type", label, msg.message_type, msgId);
            }
            if (msg.subject) {
                const text = this.getMessageText(msg.subject);
                if (text) add("subject", text, text, msgId);
            }
        }

        if (this.resModel && this.resId) {
            const recordFieldNames = Object.entries(this.searchableFields)
                .filter(([, field]) => field.source === "record")
                .map(([name]) => name);

            let record = null;
            try {
                [record] = await this.orm.read(this.resModel, [this.resId], recordFieldNames);
            } catch (e) { console.error(LOG, "record read:", e); }

            if (record) {
                for (const [fieldName, field] of Object.entries(this.searchableFields)) {
                    if (field.source !== "record") continue;
                    if (["one2many", "many2many"].includes(field.type)) continue;
                    const value = record[fieldName];
                    if (value === false || value === null || value === undefined || value === "") continue;

                    let displayName = "", rawValue = value;
                    if (field.type === "many2one") {
                        if (Array.isArray(value) && value[0]) { displayName = value[1] || ""; rawValue = value[0]; }
                        else continue;
                    } else if (field.type === "selection") {
                        const option = (field.selection || []).find(([x]) => String(x) === String(value));
                        displayName = option ? option[1] : String(value);
                    } else if (field.type === "text" || field.type === "html") {
                        const text = this.getMessageText(value);
                        if (!text || text.length > 200) continue;
                        displayName = text;
                    } else {
                        displayName = String(value);
                    }
                    add(fieldName, displayName, rawValue);
                }

                for (const [fieldName, field] of Object.entries(this.searchableFields)) {
                    if (field.source !== "record") continue;
                    if (!["one2many", "many2many"].includes(field.type)) continue;
                    if (!field.relation) continue;
                    const relatedIds = record[fieldName];
                    if (!Array.isArray(relatedIds) || !relatedIds.length) continue;

                    try {
                        const relatedFieldDefs = await this.orm.call(field.relation, "fields_get",
                            [[], ["string", "type", "relation", "selection"]]);
                        const many2oneNames = [], charOrSelectionNames = [];
                        for (const [name, def] of Object.entries(relatedFieldDefs || {})) {
                            if (["id", "create_uid", "write_uid", "create_date", "write_date",
                                 "display_name", "__last_update"].includes(name)) continue;
                            if (def.type === "many2one") many2oneNames.push(name);
                            else if (["char", "selection"].includes(def.type)) charOrSelectionNames.push(name);
                        }
                        const namesToRead = [...many2oneNames, ...charOrSelectionNames];
                        if (!namesToRead.length) continue;

                        const relatedRecords = await this.orm.read(field.relation, relatedIds.slice(0, 200), namesToRead);
                        for (const relatedRecord of relatedRecords) {
                            for (const many2oneName of many2oneNames) {
                                const value = relatedRecord[many2oneName];
                                if (Array.isArray(value) && value[0]) add(many2oneName, value[1], value[0]);
                            }
                            for (const fieldName of charOrSelectionNames) {
                                const value = relatedRecord[fieldName];
                                if (!value) continue;
                                const def = relatedFieldDefs[fieldName];
                                let label = String(value);
                                if (def.type === "selection") {
                                    const option = (def.selection || []).find(([x]) => String(x) === String(value));
                                    label = option ? option[1] : String(value);
                                }
                                add(fieldName, label, value);
                            }
                        }
                    } catch (e) { console.error(LOG, `read ${fieldName}:`, e); }
                }
            }
        }

        const messageIds = messages
            .map((m) => Number(m.id))
            .filter((id) => Number.isFinite(id) && id > 0);

        if (messageIds.length) {
            try {
                const trackingValues = await this.orm.searchRead(
                    "mail.tracking.value",
                    [["mail_message_id", "in", messageIds]],
                    [
                        "mail_message_id", "field_id",
                        "old_value_char", "new_value_char",
                        "old_value_text", "new_value_text",
                        "old_value_integer", "new_value_integer",
                        "old_value_float", "new_value_float",
                        "old_value_datetime", "new_value_datetime",
                    ],
                    { limit: 3000 }
                );

                const fieldIds = [
                    ...new Set(
                        trackingValues.map((tv) => this.getMany2OneValue(tv.field_id).id)
                            .filter(Boolean).map(Number)
                    ),
                ];
                let fieldDefsById = [];
                if (fieldIds.length) {
                    fieldDefsById = await this.orm.searchRead(
                        "ir.model.fields",
                        [["id", "in", fieldIds]],
                        ["id", "name", "field_description", "model", "ttype"],
                        { limit: fieldIds.length }
                    );
                }
                const fieldDefById = new Map(fieldDefsById.map((f) => [Number(f.id), f]));

                for (const tv of trackingValues) {
                    const messageId = Number(this.getMany2OneValue(tv.mail_message_id).id || tv.mail_message_id);
                    const fieldId = Number(this.getMany2OneValue(tv.field_id).id);
                    const fieldDef = fieldDefById.get(fieldId);
                    if (!Number.isFinite(messageId) || !messageId || !fieldDef?.name) continue;

                    const fieldName = fieldDef.name;
                    const field = this.searchableFields[fieldName];
                    if (!field) continue;

                    for (const prefix of ["old", "new"]) {
                        let raw;
                        if (field.type === "monetary" || field.type === "float") {
                            raw = tv[`${prefix}_value_float`];
                        } else if (field.type === "integer") {
                            raw = tv[`${prefix}_value_integer`];
                        } else if (field.type === "date" || field.type === "datetime") {
                            raw = tv[`${prefix}_value_datetime`];
                        } else {
                            raw = [
                                tv[`${prefix}_value_char`], tv[`${prefix}_value_text`],
                                tv[`${prefix}_value_integer`], tv[`${prefix}_value_float`],
                                tv[`${prefix}_value_datetime`],
                            ].find((v) => v !== false && v !== null && v !== undefined && v !== "");
                        }
                        if (raw === undefined || raw === null || raw === false || raw === "") continue;

                        let displayName = String(raw);
                        if (field.type === "selection") {
                            const option = (field.selection || []).find(([value]) => String(value) === String(raw));
                            displayName = option ? option[1] : String(raw);
                        }
                        add(fieldName, displayName, raw, messageId);
                    }
                }
            } catch (e) { console.error(LOG, "[Tracking] ERROR:", e); }
        }

        const allMessagesText = messages
            .map((m) => `${this.getMessageText(m.subject)} ${this.getMessageText(m.body)}`)
            .join(" ")
            .toLowerCase();

        for (const [fieldName, field] of Object.entries(this.searchableFields)) {
            if (field.type !== "selection") continue;
            if (!field.selection || !Array.isArray(field.selection)) continue;
            for (const [value, label] of field.selection) {
                if (!label || typeof label !== "string") continue;
                if (label.toLowerCase() === value.toLowerCase()) continue;
                if (!allMessagesText.includes(label.toLowerCase())) continue;
                add(fieldName, label, value);
            }
        }

        this.suggestions = suggestions;
        this.fieldValueMessageIds = fieldValueMessageIds;
        log(`extracted ${suggestions.length} suggestions`);
    },

    _currentSignature() {
        return `${this.resId}|${this.threadMessages.length}`;
    },

    async _ensureExtracted() {
        const sig = this._currentSignature();
        if (this._extractedSignature === sig && this.suggestions.length) return;
        await this.extractAllSuggestions();
        this._extractedSignature = sig;
    },

    onFiltersChanged(callback) {
        this._filterChangeListeners.add(callback);
        return () => this._filterChangeListeners.delete(callback);
    },

    notifyFiltersChanged(shouldAttemptClose = true) {
        for (const listener of this._filterChangeListeners) listener(shouldAttemptClose);
    },

    notifyDateFilterChanged() {
        const f = this.advancedFilterState.filters;
        this.notifyFiltersChanged(!!(f.dateFrom && f.dateTo));
    },

    onMessageFilterChanged() {
        const f = this.advancedFilterState.filters;
        f.activityTypeId = "";
        f.activityUserId = "";
        f.activityState = "";
        this.notifyFiltersChanged();
    },

    onActivityFilterChanged() {
        const f = this.advancedFilterState.filters;
        f.keyword = "";
        f.activeKeyword = "";
        f.activeKeywordMode = "";
        f.userId = "";
        f.messageType = "";
        f.subtypeId = "";
        clearFieldSelection(f);
        this.notifyFiltersChanged();
    },

    get threadMessages() {
        return this.state.thread?.messages || [];
    },

    get conversationAuthors() {
        const seen = new Set(); const authors = [];
        for (const m of this.threadMessages) {
            if (!m.author?.id || seen.has(m.author.id)) continue;
            seen.add(m.author.id); authors.push({ id: m.author.id, name: m.author.name || "" });
        }
        return authors.sort((a, b) => a.name.localeCompare(b.name));
    },

    get conversationMessageTypes() {
        const seen = new Set();
        for (const m of this.threadMessages) if (m.message_type) seen.add(m.message_type);
        return this.messageTypeOptions.filter((t) => seen.has(t.value));
    },

    get conversationSubtypes() {
        const seen = new Set();
        for (const m of this.threadMessages) {
            const id = m.subtype_id?.id ?? m.subtype_id;
            if (id) seen.add(Number(id));
        }
        return this.advancedFilterState.subtypes.filter((s) => seen.has(Number(s.id)));
    },

    get conversationActivities() {
        return this.state.thread?.activities || [];
    },

    get activities() {
        if (this.isMessageFilterActive) return [];

        const list = this.state.thread?.activities || [];
        const f = this.advancedFilterState.filters;
        if (!f.activityTypeId && !f.activityUserId && !f.activityState && !f.dateFrom && !f.dateTo) return list;

        return list.filter((a) => {
            const typeId = this.getMany2OneValue(a.activity_type_id).id;
            const userId = this.getMany2OneValue(a.user_id).id;
            const date = a.date_deadline || "";
            if (f.dateFrom && (!date || date < f.dateFrom)) return false;
            if (f.dateTo && (!date || date > f.dateTo)) return false;
            if (f.activityTypeId && Number(typeId) !== Number(f.activityTypeId)) return false;
            if (f.activityUserId && Number(userId) !== Number(f.activityUserId)) return false;
            if (f.activityState && a.state !== f.activityState) return false;
            return true;
        });
    },

    get isActivityFilterActive() {
        const f = this.advancedFilterState.filters;
        return !!(f.activityTypeId || f.activityUserId || f.activityState);
    },

    get isMessageFilterActive() {
        const f = this.advancedFilterState.filters;
        return !!(f.activeKeyword || f.userId || f.messageType || f.subtypeId || f.fieldValueLabel);
    },

    get activeAdvancedFilterCount() {
        const f = this.advancedFilterState.filters;
        return [
            f.dateFrom,
            f.dateTo,
            f.userId,
            f.messageType,
            f.subtypeId,
            f.activityTypeId,
            f.activityUserId,
            f.activityState,
            f.fieldValueLabel,
            f.activeKeywordMode === "message" && f.activeKeyword,
        ].filter(Boolean).length;
    },

    getMany2OneValue(value) {
        if (Array.isArray(value)) return { id: value[0] || null, name: value[1] || "" };
        if (value && typeof value === "object") {
            return { id: value.id || value.res_id || null, name: value.display_name || value.name || "" };
        }
        return { id: value || null, name: "" };
    },

    get conversationActivityTypes() {
        const seen = new Set(); const types = [];
        for (const a of this.conversationActivities) {
            const v = this.getMany2OneValue(a.activity_type_id);
            if (!v.id || seen.has(Number(v.id))) continue;
            seen.add(Number(v.id)); types.push({ id: Number(v.id), name: v.name || "" });
        }
        return types.sort((a, b) => a.name.localeCompare(b.name));
    },

    get conversationActivityUsers() {
        const seen = new Set(); const users = [];
        for (const a of this.conversationActivities) {
            const v = this.getMany2OneValue(a.user_id);
            if (!v.id || seen.has(Number(v.id))) continue;
            seen.add(Number(v.id)); users.push({ id: Number(v.id), name: v.name || "" });
        }
        return users.sort((a, b) => a.name.localeCompare(b.name));
    },

    get conversationActivityStates() {
        const seen = new Set(this.conversationActivities.map((a) => a.state).filter(Boolean));
        return (this.activityStateOptions || []).filter((s) => seen.has(s.value));
    },

    get currentSearchKeyword() {
        return this.searchMessageInput?.state?.searchTerm || "";
    },

    get searchSuggestionGroups() {
        const keyword = this.currentSearchKeyword.trim();
        if (!keyword) return [];

        const term = keyword.toLowerCase();
        const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const wordBoundaryRegex = new RegExp(`(^|[\\s\\W_])${escapeRegex(term)}([\\s\\W_]|$)`, "i");

        const groups = [{ key: "message", label: "Message", items: [], expandable: false }];

        const itemsByField = new Map();
        for (const suggestion of this.suggestions) {
            if (!itemsByField.has(suggestion.fieldName)) itemsByField.set(suggestion.fieldName, []);
            itemsByField.get(suggestion.fieldName).push(suggestion);
        }

        const fieldGroups = [];
        for (const [fieldName, items] of itemsByField) {
            const field = this.searchableFields[fieldName];
            const fieldLabel = (field?.string || fieldName).toLowerCase();
            const fieldNameLower = fieldName.toLowerCase();
            const fieldMatches = fieldLabel === term || fieldNameLower === term;
            const valueMatches = items.filter((v) =>
                wordBoundaryRegex.test(v.displayName.toLowerCase()) || v.displayName.toLowerCase() === term
            );

            if (fieldMatches) {
                const sorted = [...items].sort((a, b) => a.displayName.localeCompare(b.displayName));
                fieldGroups.push({
                    key: `field:${fieldName}`,
                    label: field?.string || fieldName,
                    fieldName,
                    fieldType: field?.type || "",
                    items: sorted.slice(0, 25),
                    expandable: sorted.length > 1,
                    _fieldMatched: true,
                });
            } else if (valueMatches.length) {
                valueMatches.sort((a, b) => {
                    const rank = (label) => (label === term ? 0 : label.startsWith(term) ? 1 : 2);
                    return rank(a.displayName.toLowerCase()) - rank(b.displayName.toLowerCase());
                });
                fieldGroups.push({
                    key: `field:${fieldName}`,
                    label: field?.string || fieldName,
                    fieldName,
                    fieldType: field?.type || "",
                    items: valueMatches.slice(0, 15),
                    expandable: valueMatches.length > 1,
                    _fieldMatched: false,
                });
            }
        }

        fieldGroups.sort((a, b) => (a._fieldMatched ? 1 : 0) - (b._fieldMatched ? 1 : 0));

        groups.push(...fieldGroups);
        log(`"${keyword}" →`, groups.map((g) => `${g.label}(${g.items.length})`));
        return groups;
    },

    clearKeywordSearch() {
        Object.assign(this.advancedFilterState.filters, createEmptyFilters());
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.notifyFiltersChanged();
    },

    clearAdvancedFilters() {
        this.clearKeywordSearch();
    },

    toggleSuggestionGroup(key) {
        this.advancedFilterState.expandedSuggestionGroup =
            this.advancedFilterState.expandedSuggestionGroup === key ? null : key;
    },

    selectSearchSuggestion(group, item = null) {
        if (group.key.startsWith("field:")) {
            if (item) this.selectFieldSuggestion(group.fieldName, item, group.label);
            return;
        }
        if (group.key === "message") this.selectMessageSuggestion();
    },

    selectFieldSuggestion(fieldName, item, fieldLabel) {
        const f = this.advancedFilterState.filters;
        f.keyword = item.displayName;
        f.activeKeyword = item.displayName;
        f.activeKeywordMode = "field";
        f.fieldName = fieldName;
        f.fieldLabel = fieldLabel;
        f.fieldValue = item.rawValue;
        f.fieldValueLabel = item.displayName;
        f.userId = ""; f.messageType = ""; f.subtypeId = "";
        f.activityTypeId = ""; f.activityUserId = ""; f.activityState = "";
        this._closeSuggestionsAndNotify();
    },

    selectMessageSuggestion() {
        const keyword = this.advancedFilterState.filters.keyword.trim();
        if (!keyword) return;
        const f = this.advancedFilterState.filters;
        f.activeKeyword = keyword;
        f.activeKeywordMode = "message";
        clearFieldSelection(f);
        this._closeSuggestionsAndNotify();
    },

    _closeSuggestionsAndNotify() {
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.notifyFiltersChanged();
    },

    get filteredMessages() {
        const messages = this.threadMessages;
        const f = this.advancedFilterState.filters;

        if (this.isActivityFilterActive) return [];

        const hasAnyFilter = !!(
            f.activeKeyword || f.dateFrom || f.dateTo ||
            f.userId || f.messageType || f.subtypeId || f.fieldValueLabel
        );
        if (!hasAnyFilter) return messages;

        let result = messages;
        const activeKeyword = (f.activeKeyword || "").trim().toLowerCase();
        const mode = f.activeKeywordMode || "";

        if (activeKeyword && mode === "message") {
            result = result.filter((m) => this._getMessageSearchText(m).includes(activeKeyword));
        }

        if (mode === "field" && f.fieldName && f.fieldValueLabel) {
            const key = `${f.fieldName}|${f.fieldValueLabel.trim().toLowerCase()}`;
            const exactMessageIds = this.fieldValueMessageIds.get(key);

            if (exactMessageIds && exactMessageIds.size) {
                result = result.filter((m) => exactMessageIds.has(Number(m.id)));
            } else {
                const needle = f.fieldValueLabel.trim().toLowerCase();
                result = result.filter((m) => this._getMessageSearchText(m).includes(needle));
            }
        }

        return result.filter((m) => {
            const date = this.getMessageDate(m);
            if (f.dateFrom && (!date || date < f.dateFrom)) return false;
            if (f.dateTo && (!date || date > f.dateTo)) return false;
            if (f.userId) {
                const authorId = m.author?.id;
                if (!authorId || Number(authorId) !== Number(f.userId)) return false;
            }
            if (f.messageType && m.message_type !== f.messageType) return false;
            if (f.subtypeId) {
                const subtypeId = m.subtype_id?.id || m.subtype_id;
                if (Number(subtypeId) !== Number(f.subtypeId)) return false;
            }
            return true;
        });
    },

    _getMessageSearchText(m) {
        return `${this.getMessageText(m.subject)} ${this.getMessageText(m.body)}`.toLowerCase();
    },

    getMessageDate(m) {
        if (!m?.date) return null;
        try {
            if (typeof m.date.toISODate === "function") return m.date.toISODate();
            if (typeof m.date === "string") return m.date.substring(0, 10);
        } catch { return null; }
        return null;
    },

    getMessageText(value) {
        if (!value) return "";
        if (typeof value === "string") {
            const container = document.createElement("div");
            container.innerHTML = value;
            return (container.textContent || container.innerText || "").replace(/<[^>]*>/g, " ").trim();
        }
        return String(value).replace(/<[^>]*>/g, " ").trim();
    },

    async exportAdvancedResults() {
        const messages = this.filteredMessages || [];
        const activities = this.activities || [];
        if (!messages.length && !activities.length) return;

        const messageIds = messages.map((m) => Number(m.id)).filter((id) => Number.isFinite(id) && id > 0);
        const activityIds = activities.map((a) => Number(a.id)).filter((id) => Number.isFinite(id) && id > 0);

        let messageAudit = [], activityAudit = [];
        try {
            [messageAudit, activityAudit] = await Promise.all([
                messageIds.length ? this.orm.searchRead("mail.message", [["id", "in", messageIds]],
                    ["id", "create_date", "create_uid", "write_date", "write_uid"],
                    { limit: messageIds.length }) : [],
                activityIds.length ? this.orm.searchRead("mail.activity", [["id", "in", activityIds]],
                    ["id", "create_date", "create_uid", "write_date", "write_uid"],
                    { limit: activityIds.length }) : [],
            ]);
        } catch {}

        const messageAuditById = new Map((messageAudit || []).map((r) => [Number(r.id), r]));
        const activityAuditById = new Map((activityAudit || []).map((r) => [Number(r.id), r]));
        const auditName = (value) => this.getMany2OneValue(value).name || "";

        const rows = [[
            "ID", "Create Date", "Created By", "Last Updated Date", "Last Updated By",
            "Date", "User / Author", "Message Type", "Subject / Summary", "Message / Note", "Result Type",
        ]];

        for (const m of messages) {
            const audit = messageAuditById.get(Number(m.id)) || {};
            rows.push([
                m.id || "", audit.create_date || "", auditName(audit.create_uid),
                audit.write_date || "", auditName(audit.write_uid), this.getMessageDate(m) || "",
                m.author?.name || "",
                this.messageTypeOptions.find((t) => t.value === m.message_type)?.label || m.message_type || "",
                this.getMessageText(m.subject), this.getMessageText(m.body), "Message",
            ]);
        }
        for (const a of activities) {
            const audit = activityAuditById.get(Number(a.id)) || {};
            rows.push([
                a.id || "", audit.create_date || "", auditName(audit.create_uid),
                audit.write_date || "", auditName(audit.write_uid), a.date_deadline || "",
                auditName(a.user_id), auditName(a.activity_type_id), a.summary || "",
                this.getMessageText(a.note), "Activity",
            ]);
        }

        const csv = rows.map((row) => row.map((value) => {
            const normalized = String(value ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\n/g, " ");
            return `"${normalized.replace(/"/g, '""')}"`;
        }).join(",")).join("\r\n");

        const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "advanced_chatter_results.csv";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },
});

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        const chatter = this.env.advancedChatterSearch;
        if (chatter && typeof chatter.onFiltersChanged === "function") {
            const unsubscribe = chatter.onFiltersChanged(() => this.render());
            onWillDestroy(unsubscribe);
        }
    },
    get filteredMessages() {
        const chatter = this.env.advancedChatterSearch;
        if (!chatter) return this.orderedMessages || [];
        const filtered = chatter.filteredMessages || [];
        return this.props.order === "asc" ? [...filtered] : [...filtered].reverse();
    },
});

patch(SearchMessageInput.prototype, {
    setup() {
        super.setup(...arguments);
        this.advancedDropdownState = useState({ expandedGroup: null });
        this.filterDropdownState = useDropdownState();

        const chatter = this.env.advancedChatterSearch;
        if (chatter) chatter.searchMessageInput = this;

        if (chatter && typeof chatter.onFiltersChanged === "function") {
            const unsubscribe = chatter.onFiltersChanged((shouldClose = true) => {
                this.render();
                if (shouldClose) this.filterDropdownState.close();
            });
            onWillDestroy(unsubscribe);
        }

        if (chatter) {
            onWillDestroy(() => {
                if (chatter.searchMessageInput === this) chatter.searchMessageInput = null;
            });
        }
    },

    clear() {
        super.clear();
        const chatter = this.env.advancedChatterSearch;
        if (chatter?.clearAdvancedFilters) chatter.clearAdvancedFilters();
    },

    toggleAdvancedGroup(key) {
        this.advancedDropdownState.expandedGroup =
            this.advancedDropdownState.expandedGroup === key ? null : key;
    },

    onKeywordSync() {
        const chatter = this.env.advancedChatterSearch;
        if (!chatter) return;
        setTimeout(() => {
            const typed = this.state.searchTerm || "";
            const f = chatter.advancedFilterState.filters;
            f.keyword = typed;
            f.activeKeyword = "";
            f.activeKeywordMode = "";
            clearFieldSelection(f);
            chatter.advancedFilterState.showSuggestions = !!typed.trim();
            this.advancedDropdownState.expandedGroup = null;
            if (typed.trim()) {
                chatter._ensureExtracted().then(() => chatter.notifyFiltersChanged(false));
            }
        }, 0);
    },

    onKeywordFocusSync() {
        const chatter = this.env.advancedChatterSearch;
        if (chatter && this.state.searchTerm.trim()) chatter.advancedFilterState.showSuggestions = true;
    },

    onKeywordBlurSync() {
        const chatter = this.env.advancedChatterSearch;
        if (!chatter) return;
        setTimeout(() => {
            chatter.advancedFilterState.showSuggestions = false;
            this.advancedDropdownState.expandedGroup = null;
        }, 200);
    },

    selectSuggestionAndSync(group, item = null) {
        const chatter = this.env.advancedChatterSearch;
        if (!chatter) return;
        chatter.selectSearchSuggestion(group, item);
    },
});


patch(FormCompiler.prototype, {
    setup() {
        super.setup(...arguments);
        const chatterCompiler = this.compilers.find((c) => c.selector === "chatter");
        if (!chatterCompiler || chatterCompiler._advancedChatterPatched) return;

        const originalFn = chatterCompiler.fn;
        chatterCompiler.fn = function (node, params) {
            const result = originalFn.call(this, node, params);
            if (!result || typeof node?.getAttribute !== "function") return result;

            const chatterComponentNode = Array.from(result.querySelectorAll("t[t-component]"))
                .find((el) => (el.getAttribute("t-component") || "").includes("Chatter"));
            if (!chatterComponentNode) {
                console.warn(LOG, "Chatter node not found");
                return result;
            }

            let options = {};
            const optionsAttr = node.getAttribute("options");
            if (optionsAttr) {
                try { options = evaluateExpr(optionsAttr) || {}; }
                catch (e) { console.error(LOG, e); }
            }

            if ("advance_search" in options) {
                setAttributes(chatterComponentNode, { advancesearch: !!options.advance_search });
            }
            if ("advance_filter" in options) {
                setAttributes(chatterComponentNode, { advancefilter: !!options.advance_filter });
            }

            return result;
        };
        chatterCompiler._advancedChatterPatched = true;
    },
});