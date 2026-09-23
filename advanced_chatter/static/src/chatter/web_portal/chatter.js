/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useEffect, useState } from "@odoo/owl";

const USEFUL_FIELD_TYPES = new Set([
    "char", "text", "many2one", "selection", "integer", "float",
    "monetary", "date", "datetime", "html", "one2many", "many2many",
]);
const EXCLUDED_RECORD_FIELDS = new Set([
    "id", "create_uid", "create_date", "write_uid", "write_date",
    "__last_update", "display_name", "access_token", "message_ids",
]);
const AUDIT_META_FIELDS = ["id", "create_date", "create_uid", "write_date", "write_uid"];
const KEPT_MESSAGE_FIELDS = ["author_id", "subtype_id", "message_type", "subject", "email_from"];

Chatter.props.push("advancesearch?", "advancefilter?");

patch(Chatter.prototype, {
    get childSubEnv() {
        return { ...super.childSubEnv, advancedChatterSearch: this };
    },
    createEmptyFilters() {
        return {
            keyword: "", activeKeyword: "", activeKeywordMode: "",
            dateFrom: "", dateTo: "", userId: "", messageType: "", subtypeId: "",
            activityTypeId: "", activityUserId: "", activityState: "",
            fieldName: "", fieldLabel: "", fieldValue: "", fieldValueLabel: "",
        };
    },
    clearFieldSelection(filters) {
        filters.fieldName = "";
        filters.fieldLabel = "";
        filters.fieldValue = "";
        filters.fieldValueLabel = "";
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
            filters: this.createEmptyFilters(),
            subtypes: [],
            activityTypes: [],
        });
        onWillStart(() => this._loadInitialData());
        useEffect(() => {
            const count = this.threadMessages.length;
            const signature = `${this.resId}|${count}`;
            if (count > 0 && this._extractedSignature !== signature) {
                this.extractAllSuggestions().then(() => {
                    this._extractedSignature = signature;
                    this.notifyFiltersChanged(false);
                });
            }
        }, () => [this.threadMessages.length, this.resId]);
    },
    async _loadInitialData() {
        this.resModel = this.props.resModel || this.props.record?.resModel || this.state.thread?.model;
        this.resId = this.props.resId || this.props.record?.resId || this.state.thread?.id;
        this.hasAdvancedChatterAccess = await this.orm.call("res.users", "check_advanced_chatter_access", []);
        if (!this.hasAdvancedChatterAccess) return;
        await Promise.all([
            this._loadSelectionOptions("mail.message", "message_type", "messageTypeOptions"),
            this._loadSelectionOptions("mail.activity", "state", "activityStateOptions"),
            this._loadSubtypes(),
            this._loadActivityTypes(),
        ]);
        await this.loadAllFields();
    },
    async _loadSelectionOptions(model, fieldName, targetProperty) {
        try {
            const fieldsInfo = await this.orm.call(model, "fields_get", [[fieldName]]);
            const selection = fieldsInfo[fieldName]?.selection || [];
            this[targetProperty] = selection.map(([value, label]) => ({ value, label }));
        } catch { /* empty */ }
    },
    async _loadSubtypes() {
        try {
            this.advancedFilterState.subtypes = await this.orm.searchRead(
                "mail.message.subtype", [], ["id", "name"], { limit: 200, order: "name asc" }
            );
        } catch { /* empty */ }
    },
    async _loadActivityTypes() {
        try {
            this.advancedFilterState.activityTypes = await this.orm.searchRead(
                "mail.activity.type", [], ["id", "name"], { limit: 200, order: "name asc" }
            );
        } catch { /* empty */ }
    },
    async loadAllFields() {
        const result = {};
        await this._collectMessageFields(result);
        if (this.resModel) await this._collectRecordFields(result);
        this.searchableFields = result;
    },
    async _collectMessageFields(result) {
        try {
            const messageFields = await this.orm.call("mail.message", "fields_get", [[], ["string", "type", "relation", "selection"]]);
            for (const [name, def] of Object.entries(messageFields || {})) {
                if (KEPT_MESSAGE_FIELDS.includes(name)) result[name] = this._buildFieldEntry(name, def, "message");
            }
        } catch { /* empty */ }
    },
    async _collectRecordFields(result) {
        try {
            const recordFields = await this.orm.call(this.resModel, "fields_get", [[], ["string", "type", "relation", "selection", "searchable"]]);
            for (const [name, def] of Object.entries(recordFields || {})) {
                if (EXCLUDED_RECORD_FIELDS.has(name)) continue;
                if (!USEFUL_FIELD_TYPES.has(def.type)) continue;
                if (def.searchable === false) continue;
                if (result[name]) continue;
                result[name] = this._buildFieldEntry(name, def, "record");
            }
        } catch { /* empty */ }
    },
    _buildFieldEntry(name, def, source) {
        return { name, string: def.string, type: def.type, relation: def.relation, selection: def.selection, source };
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
                    fieldName, fieldLabel: field?.string || fieldName, fieldType: field?.type || "",
                    displayName: label, rawValue,
                });
            }
            if (messageId !== null && messageId !== undefined) {
                const id = Number(messageId);
                if (Number.isFinite(id)) {
                    if (!fieldValueMessageIds.has(key)) fieldValueMessageIds.set(key, new Set());
                    fieldValueMessageIds.get(key).add(id);
                }
            }
        };
        const messages = this.threadMessages;
        this._addMessageFieldSuggestions(messages, add);
        await this._addRecordFieldSuggestions(add);
        await this._addTrackingValueSuggestions(messages, add);
        this._addMatchedSelectionLabels(messages, add);
        this.suggestions = suggestions;
        this.fieldValueMessageIds = fieldValueMessageIds;
    },
    _addMessageFieldSuggestions(messages, add) {
        const messageTypeLabels = new Map(this.messageTypeOptions.map((t) => [t.value, t.label]));
        for (const msg of messages) {
            const msgId = msg.id;
            if (msg.author?.id && msg.author?.name) add("author_id", msg.author.name, msg.author.id, msgId);
            if (msg.email_from && typeof msg.email_from === "string") add("email_from", msg.email_from, msg.email_from, msgId);
            if (msg.subtype_id?.id && msg.subtype_id?.name) add("subtype_id", msg.subtype_id.name, msg.subtype_id.id, msgId);
            if (msg.message_type) add("message_type", messageTypeLabels.get(msg.message_type) || msg.message_type, msg.message_type, msgId);
            if (msg.subject) {
                const text = this.getMessageText(msg.subject);
                if (text) add("subject", text, text, msgId);
            }
        }
    },
    async _addRecordFieldSuggestions(add) {
        if (!this.resModel || !this.resId) return;
        const recordFieldNames = Object.entries(this.searchableFields)
            .filter(([, field]) => field.source === "record")
            .map(([name]) => name);
        let record = null;
        try {
            [record] = await this.orm.read(this.resModel, [this.resId], recordFieldNames);
        } catch { /* empty */ }
        if (!record) return;
        this._addScalarRecordFields(record, add);
        await this._addRelationalRecordFields(record, add);
    },
    _addScalarRecordFields(record, add) {
        for (const [fieldName, field] of Object.entries(this.searchableFields)) {
            if (field.source !== "record") continue;
            if (["one2many", "many2many"].includes(field.type)) continue;
            const value = record[fieldName];
            if (value === false || value === null || value === undefined || value === "") continue;
            let displayName = "";
            let rawValue = value;
            if (field.type === "many2one") {
                if (Array.isArray(value) && value[0]) {
                    displayName = value[1] || "";
                    rawValue = value[0];
                } else continue;
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
    },
    async _addRelationalRecordFields(record, add) {
        for (const [fieldName, field] of Object.entries(this.searchableFields)) {
            if (field.source !== "record") continue;
            if (!["one2many", "many2many"].includes(field.type)) continue;
            if (!field.relation) continue;
            const relatedIds = record[fieldName];
            if (!Array.isArray(relatedIds) || !relatedIds.length) continue;
            try {
                const relatedFieldDefs = await this.orm.call(field.relation, "fields_get", [[], ["string", "type", "relation", "selection"]]);
                const many2oneNames = [];
                const charOrSelectionNames = [];
                for (const [name, def] of Object.entries(relatedFieldDefs || {})) {
                    if (["id", "create_uid", "write_uid", "create_date", "write_date", "display_name", "__last_update"].includes(name)) continue;
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
                    for (const relFieldName of charOrSelectionNames) {
                        const value = relatedRecord[relFieldName];
                        if (!value) continue;
                        const def = relatedFieldDefs[relFieldName];
                        let label = String(value);
                        if (def.type === "selection") {
                            const option = (def.selection || []).find(([x]) => String(x) === String(value));
                            label = option ? option[1] : String(value);
                        }
                        add(relFieldName, label, value);
                    }
                }
            } catch { /* empty */ }
        }
    },
    async _addTrackingValueSuggestions(messages, add) {
        const messageIds = messages.map((m) => Number(m.id)).filter((id) => Number.isFinite(id) && id > 0);
        if (!messageIds.length) return;
        try {
            const trackingValues = await this.orm.searchRead(
                "mail.tracking.value", [["mail_message_id", "in", messageIds]],
                ["mail_message_id", "field_id", "old_value_char", "new_value_char", "old_value_text", "new_value_text",
                 "old_value_integer", "new_value_integer", "old_value_float", "new_value_float",
                 "old_value_datetime", "new_value_datetime"],
                { limit: 3000 }
            );
            const fieldDefById = await this._loadTrackingFieldDefs(trackingValues);
            for (const tv of trackingValues) {
                const messageId = Number(this.getMany2OneValue(tv.mail_message_id).id || tv.mail_message_id);
                const fieldId = Number(this.getMany2OneValue(tv.field_id).id);
                const fieldDef = fieldDefById.get(fieldId);
                if (!Number.isFinite(messageId) || !messageId || !fieldDef?.name) continue;
                const fieldName = fieldDef.name;
                const field = this.searchableFields[fieldName];
                if (!field) continue;
                for (const prefix of ["old", "new"]) {
                    const raw = this._readTrackingValue(tv, prefix, field.type);
                    if (raw === undefined || raw === null || raw === false || raw === "") continue;
                    let displayName = String(raw);
                    if (field.type === "selection") {
                        const option = (field.selection || []).find(([value]) => String(value) === String(raw));
                        displayName = option ? option[1] : String(raw);
                    }
                    add(fieldName, displayName, raw, messageId);
                }
            }
        } catch { /* empty */ }
    },
    async _loadTrackingFieldDefs(trackingValues) {
        const fieldIds = [...new Set(trackingValues.map((tv) => this.getMany2OneValue(tv.field_id).id).filter(Boolean).map(Number))];
        if (!fieldIds.length) return new Map();
        const fieldDefsById = await this.orm.searchRead(
            "ir.model.fields", [["id", "in", fieldIds]], ["id", "name", "field_description", "model", "ttype"], { limit: fieldIds.length }
        );
        return new Map(fieldDefsById.map((f) => [Number(f.id), f]));
    },
    _readTrackingValue(tv, prefix, fieldType) {
        if (fieldType === "monetary" || fieldType === "float") return tv[`${prefix}_value_float`];
        if (fieldType === "integer") return tv[`${prefix}_value_integer`];
        if (fieldType === "date" || fieldType === "datetime") return tv[`${prefix}_value_datetime`];
        return [
            tv[`${prefix}_value_char`], tv[`${prefix}_value_text`],
            tv[`${prefix}_value_integer`], tv[`${prefix}_value_float`], tv[`${prefix}_value_datetime`],
        ].find((v) => v !== false && v !== null && v !== undefined && v !== "");
    },
    _addMatchedSelectionLabels(messages, add) {
        const allMessagesText = messages
            .map((m) => `${this.getMessageText(m.subject)} ${this.getMessageText(m.body)}`)
            .join(" ").toLowerCase();
        for (const [fieldName, field] of Object.entries(this.searchableFields)) {
            if (field.type !== "selection") continue;
            if (!field.selection || !Array.isArray(field.selection)) continue;
            for (const [value, label] of field.selection) {
                if (!label || typeof label !== "string") continue;
                if (String(label).toLowerCase() === String(value).toLowerCase()) continue;
                if (!allMessagesText.includes(label.toLowerCase())) continue;
                add(fieldName, label, value);
            }
        }
    },
    _currentSignature() {
        return `${this.resId}|${this.threadMessages.length}`;
    },
    async _ensureExtracted() {
        const signature = this._currentSignature();
        if (this._extractedSignature === signature && this.suggestions.length) return;
        await this.extractAllSuggestions();
        this._extractedSignature = signature;
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
        this.clearFieldSelection(f);
        this.notifyFiltersChanged();
    },
    get threadMessages() {
        return this.state.thread?.messages || [];
    },
    get conversationAuthors() {
        const seen = new Set();
        const authors = [];
        for (const m of this.threadMessages) {
            if (!m.author?.id || seen.has(m.author.id)) continue;
            seen.add(m.author.id);
            authors.push({ id: m.author.id, name: m.author.name || "" });
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
            f.dateFrom, f.dateTo, f.userId, f.messageType, f.subtypeId,
            f.activityTypeId, f.activityUserId, f.activityState,
            f.fieldValueLabel, f.activeKeywordMode === "message" && f.activeKeyword,
        ].filter(Boolean).length;
    },
    getMany2OneValue(value) {
        if (Array.isArray(value)) return { id: value[0] || null, name: value[1] || "" };
        if (value && typeof value === "object") return { id: value.id || value.res_id || null, name: value.display_name || value.name || "" };
        return { id: value || null, name: "" };
    },
    get conversationActivityTypes() {
        return this._uniqueMany2OneList(this.conversationActivities, "activity_type_id");
    },
    get conversationActivityUsers() {
        return this._uniqueMany2OneList(this.conversationActivities, "user_id");
    },
    _uniqueMany2OneList(records, fieldName) {
        const seen = new Set();
        const items = [];
        for (const record of records) {
            const v = this.getMany2OneValue(record[fieldName]);
            if (!v.id || seen.has(Number(v.id))) continue;
            seen.add(Number(v.id));
            items.push({ id: Number(v.id), name: v.name || "" });
        }
        return items.sort((a, b) => a.name.localeCompare(b.name));
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
        const wordBoundaryRegex = this._buildWordBoundaryRegex(term);
        const groups = [{ key: "message", label: "Message", items: [], expandable: false }];
        const itemsByField = new Map();
        for (const suggestion of this.suggestions) {
            if (!itemsByField.has(suggestion.fieldName)) itemsByField.set(suggestion.fieldName, []);
            itemsByField.get(suggestion.fieldName).push(suggestion);
        }
        const fieldGroups = [];
        for (const [fieldName, items] of itemsByField) {
            const group = this._buildFieldSuggestionGroup(fieldName, items, term, wordBoundaryRegex);
            if (group) fieldGroups.push(group);
        }
        fieldGroups.sort((a, b) => (a._fieldMatched ? 1 : 0) - (b._fieldMatched ? 1 : 0));
        groups.push(...fieldGroups);
        return groups;
    },
    _buildWordBoundaryRegex(term) {
        const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        return new RegExp(`(^|[\\s\\W_])${escapeRegex(term)}([\\s\\W_]|$)`, "i");
    },
    _buildFieldSuggestionGroup(fieldName, items, term, wordBoundaryRegex) {
        const field = this.searchableFields[fieldName];
        const fieldLabel = (field?.string || fieldName).toLowerCase();
        const fieldNameLower = fieldName.toLowerCase();
        const fieldMatches = fieldLabel === term || fieldNameLower === term;
        const valueMatches = items.filter((v) => wordBoundaryRegex.test(v.displayName.toLowerCase()) || v.displayName.toLowerCase() === term);
        if (fieldMatches) {
            const sorted = [...items].sort((a, b) => a.displayName.localeCompare(b.displayName));
            return {
                key: `field:${fieldName}`, label: field?.string || fieldName, fieldName, fieldType: field?.type || "",
                items: sorted.slice(0, 25), expandable: sorted.length > 1, _fieldMatched: true,
            };
        }
        if (valueMatches.length) {
            valueMatches.sort((a, b) => {
                const rank = (label) => (label === term ? 0 : label.startsWith(term) ? 1 : 2);
                return rank(a.displayName.toLowerCase()) - rank(b.displayName.toLowerCase());
            });
            return {
                key: `field:${fieldName}`, label: field?.string || fieldName, fieldName, fieldType: field?.type || "",
                items: valueMatches.slice(0, 15), expandable: valueMatches.length > 1, _fieldMatched: false,
            };
        }
        return null;
    },
    clearKeywordSearch() {
        Object.assign(this.advancedFilterState.filters, this.createEmptyFilters());
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.notifyFiltersChanged();
    },
    clearAdvancedFilters() {
        this.clearKeywordSearch();
    },
    toggleSuggestionGroup(key) {
        this.advancedFilterState.expandedSuggestionGroup = this.advancedFilterState.expandedSuggestionGroup === key ? null : key;
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
        f.userId = "";
        f.messageType = "";
        f.subtypeId = "";
        f.activityTypeId = "";
        f.activityUserId = "";
        f.activityState = "";
        this._closeSuggestionsAndNotify();
    },
    selectMessageSuggestion() {
        const f = this.advancedFilterState.filters;
        const keyword = f.keyword.trim();
        if (!keyword) return;
        f.activeKeyword = keyword;
        f.activeKeywordMode = "message";
        this.clearFieldSelection(f);
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
        const hasAnyFilter = !!(f.activeKeyword || f.dateFrom || f.dateTo || f.userId || f.messageType || f.subtypeId || f.fieldValueLabel);
        if (!hasAnyFilter) return messages;
        let result = this._applyKeywordFilter(messages, f);
        result = this._applyFieldValueFilter(result, f);
        return this._applyStructuredFilters(result, f);
    },
    _applyKeywordFilter(messages, f) {
        const activeKeyword = (f.activeKeyword || "").trim().toLowerCase();
        if (activeKeyword && f.activeKeywordMode === "message") return messages.filter((m) => this._getMessageSearchText(m).includes(activeKeyword));
        return messages;
    },
    _applyFieldValueFilter(messages, f) {
        if (f.activeKeywordMode !== "field" || !f.fieldName || !f.fieldValueLabel) return messages;
        const needle = f.fieldValueLabel.trim().toLowerCase();
        const key = `${f.fieldName}|${needle}`;
        const messageIds = this.fieldValueMessageIds.get(key);
        if (messageIds && messageIds.size) return messages.filter((m) => messageIds.has(Number(m.id)));
        return messages.filter((m) => this._getMessageSearchText(m).includes(needle));
    },
    _applyStructuredFilters(messages, f) {
        return messages.filter((m) => {
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
        } catch {
            return null;
        }
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
        const { messageAuditById, activityAuditById } = await this._fetchAuditData(messages, activities);
        const rows = this._buildExportRows(messages, activities, messageAuditById, activityAuditById);
        this._downloadCsv(rows, "advanced_chatter_results.csv");
    },
    async _fetchAuditData(messages, activities) {
        const messageIds = messages.map((m) => Number(m.id)).filter((id) => Number.isFinite(id) && id > 0);
        const activityIds = activities.map((a) => Number(a.id)).filter((id) => Number.isFinite(id) && id > 0);
        let messageAudit = [];
        let activityAudit = [];
        try {
            [messageAudit, activityAudit] = await Promise.all([
                messageIds.length ? this.orm.searchRead("mail.message", [["id", "in", messageIds]], AUDIT_META_FIELDS, { limit: messageIds.length }) : [],
                activityIds.length ? this.orm.searchRead("mail.activity", [["id", "in", activityIds]], AUDIT_META_FIELDS, { limit: activityIds.length }) : [],
            ]);
        } catch {
            messageAudit = [];
            activityAudit = [];
        }
        return {
            messageAuditById: new Map((messageAudit || []).map((r) => [Number(r.id), r])),
            activityAuditById: new Map((activityAudit || []).map((r) => [Number(r.id), r])),
        };
    },
    _buildExportRows(messages, activities, messageAuditById, activityAuditById) {
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
        return rows;
    },
    _downloadCsv(rows, filename) {
        const csv = rows.map((row) => row.map((value) => {
            const normalized = String(value ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\n/g, " ");
            return `"${normalized.replace(/"/g, '""')}"`;
        }).join(",")).join("\r\n");
        const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },
});