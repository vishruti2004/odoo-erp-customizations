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
const log = (...a) => console.log(LOG, ...a);

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
            filters: {
                keyword: "", activeKeyword: "", activeKeywordMode: "",
                dateFrom: "", dateTo: "", userId: "", messageType: "", subtypeId: "",
                activityTypeId: "", activityUserId: "", activityState: "",
                fieldName: "", fieldLabel: "", fieldValue: "", fieldValueLabel: "",
            },
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
        const USEFUL = new Set([
            "char", "text", "many2one", "selection", "integer", "float",
            "monetary", "date", "datetime", "html",
            "one2many", "many2many",
        ]);
        const EXCLUDE = new Set([
            "id", "create_uid", "create_date", "write_uid", "write_date",
            "__last_update", "display_name", "access_token", "message_ids",
        ]);

        try {
            const f = await this.orm.call("mail.message", "fields_get",
                [[], ["string", "type", "relation", "selection"]]);
            const KEEP = ["author_id", "subtype_id", "message_type", "subject", "email_from"];
            for (const [n, d] of Object.entries(f || {})) {
                if (!KEEP.includes(n)) continue;
                result[n] = {
                    name: n, string: d.string, type: d.type,
                    relation: d.relation, selection: d.selection,
                    source: "message",
                };
            }
        } catch (e) { console.error(LOG, e); }

        if (this.resModel) {
            try {
                const f = await this.orm.call(this.resModel, "fields_get",
                    [[], ["string", "type", "relation", "selection", "searchable"]]);
                for (const [n, d] of Object.entries(f || {})) {
                    if (EXCLUDE.has(n)) continue;
                    if (!USEFUL.has(d.type)) continue;
                    if (d.searchable === false) continue;
                    if (result[n]) continue;
                    result[n] = {
                        name: n, string: d.string, type: d.type,
                        relation: d.relation, selection: d.selection,
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
            const dn = String(displayName).trim();
            if (!dn || dn === "false" || dn === "undefined") return;
            const key = `${fieldName}|${dn.toLowerCase()}`;

            if (!seen.has(key)) {
                seen.add(key);
                const field = this.searchableFields[fieldName];
                suggestions.push({
                    fieldName,
                    fieldLabel: field?.string || fieldName,
                    fieldType: field?.type || "",
                    displayName: dn,
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
        const typeLabelMap = new Map(this.messageTypeOptions.map((t) => [t.value, t.label]));
        for (const msg of messages) {
            const msgId = msg.id;
            if (msg.author?.id && msg.author?.name) add("author_id", msg.author.name, msg.author.id, msgId);
            if (msg.email_from && typeof msg.email_from === "string") add("email_from", msg.email_from, msg.email_from, msgId);
            if (msg.subtype_id?.id && msg.subtype_id?.name) add("subtype_id", msg.subtype_id.name, msg.subtype_id.id, msgId);
            if (msg.message_type) {
                const lbl = typeLabelMap.get(msg.message_type) || msg.message_type;
                add("message_type", lbl, msg.message_type, msgId);
            }
            if (msg.subject) {
                const t = this.getMessageText(msg.subject);
                if (t) add("subject", t, t, msgId);
            }
        }

        if (this.resModel && this.resId) {
            const recordFieldNames = Object.entries(this.searchableFields)
                .filter(([, f]) => f.source === "record")
                .map(([n]) => n);

            let record = null;
            try {
                [record] = await this.orm.read(this.resModel, [this.resId], recordFieldNames);
            } catch (e) { console.error(LOG, "record read:", e); }

            if (record) {
                for (const [fn, field] of Object.entries(this.searchableFields)) {
                    if (field.source !== "record") continue;
                    if (["one2many", "many2many"].includes(field.type)) continue;
                    const v = record[fn];
                    if (v === false || v === null || v === undefined || v === "") continue;

                    let displayName = "", rawValue = v;
                    if (field.type === "many2one") {
                        if (Array.isArray(v) && v[0]) { displayName = v[1] || ""; rawValue = v[0]; }
                        else continue;
                    } else if (field.type === "selection") {
                        const f = (field.selection || []).find(([x]) => String(x) === String(v));
                        displayName = f ? f[1] : String(v);
                    } else if (field.type === "text" || field.type === "html") {
                        const t = this.getMessageText(v);
                        if (!t || t.length > 200) continue;
                        displayName = t;
                    } else {
                        displayName = String(v);
                    }
                    add(fn, displayName, rawValue);
                }

                for (const [fn, field] of Object.entries(this.searchableFields)) {
                    if (field.source !== "record") continue;
                    if (!["one2many", "many2many"].includes(field.type)) continue;
                    if (!field.relation) continue;
                    const ids = record[fn];
                    if (!Array.isArray(ids) || !ids.length) continue;

                    try {
                        const relFieldsRaw = await this.orm.call(field.relation, "fields_get",
                            [[], ["string", "type", "relation", "selection"]]);
                        const m2oNames = [], charNames = [];
                        for (const [n, d] of Object.entries(relFieldsRaw || {})) {
                            if (["id", "create_uid", "write_uid", "create_date", "write_date",
                                 "display_name", "__last_update"].includes(n)) continue;
                            if (d.type === "many2one") m2oNames.push(n);
                            else if (["char", "selection"].includes(d.type)) charNames.push(n);
                        }
                        const readNames = [...m2oNames, ...charNames];
                        if (!readNames.length) continue;

                        const relRecords = await this.orm.read(field.relation, ids.slice(0, 200), readNames);
                        for (const rr of relRecords) {
                            for (const m of m2oNames) {
                                const mv = rr[m];
                                if (Array.isArray(mv) && mv[0]) add(m, mv[1], mv[0]);
                            }
                            for (const c of charNames) {
                                const cv = rr[c];
                                if (!cv) continue;
                                const d = relFieldsRaw[c];
                                let lbl = String(cv);
                                if (d.type === "selection") {
                                    const f = (d.selection || []).find(([x]) => String(x) === String(cv));
                                    lbl = f ? f[1] : String(cv);
                                }
                                add(c, lbl, cv);
                            }
                        }
                    } catch (e) { console.error(LOG, `read ${fn}:`, e); }
                }
            }
        }

        const messageIds = messages
            .map((m) => Number(m.id))
            .filter((id) => Number.isFinite(id) && id > 0);

        if (messageIds.length) {
            try {
                const tvs = await this.orm.searchRead(
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
                        tvs.map((tv) => this.getMany2OneValue(tv.field_id).id)
                            .filter(Boolean).map(Number)
                    ),
                ];

                let irFields = [];
                if (fieldIds.length) {
                    irFields = await this.orm.searchRead(
                        "ir.model.fields",
                        [["id", "in", fieldIds]],
                        ["id", "name", "field_description", "model", "ttype"],
                        { limit: fieldIds.length }
                    );
                }

                const fieldMap = new Map(
                    irFields.map((field) => [Number(field.id), field])
                );

                for (const tv of tvs) {
                    const tvMessageId = Number(
                        this.getMany2OneValue(tv.mail_message_id).id || tv.mail_message_id
                    );
                    const fieldId = Number(this.getMany2OneValue(tv.field_id).id);
                    const fieldInfo = fieldMap.get(fieldId);

                    if (!Number.isFinite(tvMessageId) || !tvMessageId || !fieldInfo?.name) continue;

                    const fieldName = fieldInfo.name;
                    const field = this.searchableFields[fieldName];
                    if (!field) continue;

                    for (const prefix of ["old", "new"]) {
                        const raw = [
                            tv[`${prefix}_value_char`], tv[`${prefix}_value_text`],
                            tv[`${prefix}_value_integer`], tv[`${prefix}_value_float`],
                            tv[`${prefix}_value_monetary`], tv[`${prefix}_value_datetime`],
                        ].find((v) => v !== false && v !== null && v !== undefined && v !== "");

                        if (raw === undefined || raw === null) continue;

                        let displayName = String(raw);
                        if (field.type === "selection") {
                            const option = (field.selection || []).find(
                                ([value]) => String(value) === String(raw)
                            );
                            displayName = option ? option[1] : String(raw);
                        }

                        add(fieldName, displayName, raw, tvMessageId);
                    }
                }
            } catch (e) { console.error(LOG, "[Tracking] ERROR:", e); }
        }

        for (const [fieldName, field] of Object.entries(this.searchableFields)) {
            if (field.type !== "selection") continue;
            if (!field.selection || !Array.isArray(field.selection)) continue;
            for (const [value, label] of field.selection) {
                if (!label || typeof label !== "string") continue;
                if (label.toLowerCase() === value.toLowerCase()) continue;
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

    onFiltersChanged(cb) {
        this._filterChangeListeners.add(cb);
        return () => this._filterChangeListeners.delete(cb);
    },

    notifyFiltersChanged(shouldAttemptClose = true) {
        for (const l of this._filterChangeListeners) l(shouldAttemptClose);
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
        f.fieldName = "";
        f.fieldLabel = "";
        f.fieldValue = "";
        f.fieldValueLabel = "";
        this.notifyFiltersChanged();
    },

    onDateInputClick(ev) {
        const input = ev.target;
        if (input && typeof input.showPicker === "function") {
            try {
                input.showPicker();
            } catch (e) {
            }
        }
    },

    get threadMessages() {
        return this.state.thread?.messages || this.state.thread?.orderedMessages || [];
    },

    get conversationAuthors() {
        const seen = new Set(); const r = [];
        for (const m of this.threadMessages) {
            if (!m.author?.id || seen.has(m.author.id)) continue;
            seen.add(m.author.id); r.push({ id: m.author.id, name: m.author.name || "" });
        }
        return r.sort((a, b) => a.name.localeCompare(b.name));
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
    get conversationActivities() { return this.state.thread?.activities || []; },
    get activities() {
        const list = this.state.thread?.activities || [];
        const f = this.advancedFilterState.filters;
        if (!f.activityTypeId && !f.activityUserId && !f.activityState && !f.dateFrom && !f.dateTo) return list;
        return list.filter((a) => {
            const tid = this.getMany2OneValue(a.activity_type_id).id;
            const uid = this.getMany2OneValue(a.user_id).id;
            const d = a.date_deadline || "";
            if (f.dateFrom && (!d || d < f.dateFrom)) return false;
            if (f.dateTo && (!d || d > f.dateTo)) return false;
            if (f.activityTypeId && Number(tid) !== Number(f.activityTypeId)) return false;
            if (f.activityUserId && Number(uid) !== Number(f.activityUserId)) return false;
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
        return !!(
            f.activeKeyword ||
            f.userId ||
            f.messageType ||
            f.subtypeId ||
            f.fieldValueLabel
        );
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

    getMany2OneValue(v) {
        if (Array.isArray(v)) return { id: v[0] || null, name: v[1] || "" };
        if (v && typeof v === "object") return { id: v.id || v.res_id || null, name: v.display_name || v.name || "" };
        return { id: v || null, name: "" };
    },
    get conversationActivityTypes() {
        const seen = new Set(); const r = [];
        for (const a of this.conversationActivities) {
            const v = this.getMany2OneValue(a.activity_type_id);
            if (!v.id || seen.has(Number(v.id))) continue;
            seen.add(Number(v.id)); r.push({ id: Number(v.id), name: v.name || "" });
        }
        return r.sort((a, b) => a.name.localeCompare(b.name));
    },
    get conversationActivityUsers() {
        const seen = new Set(); const r = [];
        for (const a of this.conversationActivities) {
            const v = this.getMany2OneValue(a.user_id);
            if (!v.id || seen.has(Number(v.id))) continue;
            seen.add(Number(v.id)); r.push({ id: Number(v.id), name: v.name || "" });
        }
        return r.sort((a, b) => a.name.localeCompare(b.name));
    },
    get conversationActivityStates() {
        const seen = new Set(this.conversationActivities.map((a) => a.state).filter(Boolean));
        return (this.activityStateOptions || []).filter((s) => seen.has(s.value));
    },
    get currentSearchKeyword() { return this.searchMessageInput?.state?.searchTerm || ""; },

    get searchSuggestionGroups() {
        const keyword = this.currentSearchKeyword.trim();
        if (!keyword) return [];

        const term = keyword.toLowerCase();
        const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const wordRegex = new RegExp(
            `(^|[\\s\\W_])${escapeRegex(term)}([\\s\\W_]|$)`, "i"
        );

        const groups = [];
        groups.push({ key: "message", label: "Message", items: [], expandable: false });

        const byField = new Map();
        for (const v of this.suggestions) {
            if (!byField.has(v.fieldName)) byField.set(v.fieldName, []);
            byField.get(v.fieldName).push(v);
        }

        const fieldGroups = [];

        for (const [fieldName, items] of byField) {
            const field = this.searchableFields[fieldName];
            const fieldLabel = (field?.string || fieldName).toLowerCase();
            const fieldNameLower = fieldName.toLowerCase();

            const fieldMatches =
                fieldLabel === term ||
                fieldNameLower === term ||
                wordRegex.test(fieldLabel) ||
                wordRegex.test(fieldNameLower);

            const valueMatches = items.filter((v) =>
                wordRegex.test(v.displayName.toLowerCase()) ||
                v.displayName.toLowerCase() === term
            );

            if (fieldMatches) {
                const sorted = [...items].sort((a, b) =>
                    a.displayName.localeCompare(b.displayName)
                );
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
                    const aL = a.displayName.toLowerCase();
                    const bL = b.displayName.toLowerCase();
                    const rank = (s) => s === term ? 0 : (s.startsWith(term) ? 1 : 2);
                    return rank(aL) - rank(bL);
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

        fieldGroups.sort((a, b) =>
            (a._fieldMatched ? 1 : 0) - (b._fieldMatched ? 1 : 0)
        );

        groups.push(...fieldGroups);
        log(`"${keyword}" →`, groups.map((x) => `${x.label}(${x.items.length})`));
        return groups;
    },

    onKeywordInput(ev) {
        const f = this.advancedFilterState.filters;
        f.keyword = ev.target.value;
        f.activeKeyword = ""; f.activeKeywordMode = "";
        f.fieldName = ""; f.fieldLabel = ""; f.fieldValue = ""; f.fieldValueLabel = "";
        this.advancedFilterState.showSuggestions = !!ev.target.value.trim();
        this.advancedFilterState.expandedSuggestionGroup = null;
        if (ev.target.value.trim()) {
            this._ensureExtracted().then(() => this.notifyFiltersChanged(false));
        }
    },

    onKeywordFocus() {
        if (this.advancedFilterState.filters.keyword.trim()) {
            this.advancedFilterState.showSuggestions = true;
        }
    },

    clearKeywordSearch() {
        const f = this.advancedFilterState.filters;
        Object.assign(f, {
            keyword: "", activeKeyword: "", activeKeywordMode: "",
            dateFrom: "", dateTo: "", userId: "", messageType: "", subtypeId: "",
            activityTypeId: "", activityUserId: "", activityState: "",
            fieldName: "", fieldLabel: "", fieldValue: "", fieldValueLabel: "",
        });
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.notifyFiltersChanged();
    },

    onKeywordBlur() {
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
    },

    onKeywordKeydown(ev) {
        if (ev.key === "Enter") {
            const k = this.advancedFilterState.filters.keyword.trim();
            if (!k) return;
            const f = this.advancedFilterState.filters;
            f.activeKeyword = k; f.activeKeywordMode = "message";
            f.fieldName = ""; f.fieldLabel = ""; f.fieldValue = ""; f.fieldValueLabel = "";
            f.activityTypeId = ""; f.activityUserId = ""; f.activityState = "";
            this.advancedFilterState.showSuggestions = false;
            this.advancedFilterState.expandedSuggestionGroup = null;
            this.notifyFiltersChanged();
        }
        if (ev.key === "Escape") {
            this.advancedFilterState.showSuggestions = false;
            this.advancedFilterState.expandedSuggestionGroup = null;
        }
    },

    toggleSuggestionGroup(k) {
        this.advancedFilterState.expandedSuggestionGroup =
            this.advancedFilterState.expandedSuggestionGroup === k ? null : k;
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
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.notifyFiltersChanged();
    },

    selectMessageSuggestion() {
        const k = this.advancedFilterState.filters.keyword.trim();
        if (!k) return;
        const f = this.advancedFilterState.filters;
        f.activeKeyword = k; f.activeKeywordMode = "message";
        f.fieldName = ""; f.fieldLabel = ""; f.fieldValue = ""; f.fieldValueLabel = "";
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.notifyFiltersChanged();
    },

    clearAdvancedFilters() { this.clearKeywordSearch(); },

    get filteredMessages() {
        const messages = this.threadMessages;
        const f = this.advancedFilterState.filters;
        if (this.isActivityFilterActive) return [];

        const hasAny = !!(f.activeKeyword || f.dateFrom || f.dateTo ||
            f.userId || f.messageType || f.subtypeId || f.fieldValueLabel);
        if (!hasAny) return messages;

        let result = messages;
        const ak = (f.activeKeyword || "").trim().toLowerCase();
        const mode = f.activeKeywordMode || "";

        if (ak && mode === "message") {
            result = result.filter((m) => {
                const b = this.getMessageText(m.body);
                const s = this.getMessageText(m.subject);
                return `${s} ${b}`.toLowerCase().includes(ak);
            });
        }
        if (mode === "field" && f.fieldName && f.fieldValueLabel) {
            const key = `${f.fieldName}|${f.fieldValueLabel.trim().toLowerCase()}`;
            const exactIds = this.fieldValueMessageIds.get(key);

            if (exactIds && exactIds.size) {
                result = result.filter((m) => exactIds.has(Number(m.id)));
            } else {
                const needle = f.fieldValueLabel.trim().toLowerCase();
                result = result.filter((m) => {
                    const b = this.getMessageText(m.body);
                    const s = this.getMessageText(m.subject);
                    return `${s} ${b}`.toLowerCase().includes(needle);
                });
            }
        }
        return result.filter((m) => {
            const d = this.getMessageDate(m);
            if (f.dateFrom && (!d || d < f.dateFrom)) return false;
            if (f.dateTo && (!d || d > f.dateTo)) return false;
            if (f.userId) {
                const aid = m.author?.id;
                if (!aid || Number(aid) !== Number(f.userId)) return false;
            }
            if (f.messageType && m.message_type !== f.messageType) return false;
            if (f.subtypeId) {
                const sid = m.subtype_id?.id || m.subtype_id;
                if (Number(sid) !== Number(f.subtypeId)) return false;
            }
            return true;
        });
    },

    get filteredActivities() {
        if (this.isMessageFilterActive) return [];
        return this.activities;
    },

    getMessageDate(m) {
        if (!m?.date) return null;
        try {
            if (typeof m.date.toISODate === "function") return m.date.toISODate();
            if (typeof m.date === "string") return m.date.substring(0, 10);
        } catch { return null; }
        return null;
    },

    getMessageText(v) {
        if (!v) return "";
        if (typeof v === "string") {
            const c = document.createElement("div");
            c.innerHTML = v;
            return (c.textContent || c.innerText || "").replace(/<[^>]*>/g, " ").trim();
        }
        return String(v).replace(/<[^>]*>/g, " ").trim();
    },

    async exportAdvancedResults() {
        const messages = this.filteredMessages || [];
        const activities = this.filteredActivities || [];
        if (!messages.length && !activities.length) return;

        const mIds = messages.map((m) => Number(m.id)).filter((id) => Number.isFinite(id) && id > 0);
        const aIds = activities.map((a) => Number(a.id)).filter((id) => Number.isFinite(id) && id > 0);
        let mAudit = [], aAudit = [];
        try {
            [mAudit, aAudit] = await Promise.all([
                mIds.length ? this.orm.searchRead("mail.message", [["id", "in", mIds]],
                    ["id", "create_date", "create_uid", "write_date", "write_uid"],
                    { limit: mIds.length }) : [],
                aIds.length ? this.orm.searchRead("mail.activity", [["id", "in", aIds]],
                    ["id", "create_date", "create_uid", "write_date", "write_uid"],
                    { limit: aIds.length }) : [],
            ]);
        } catch { }
        const mMap = new Map((mAudit || []).map((r) => [Number(r.id), r]));
        const aMap = new Map((aAudit || []).map((r) => [Number(r.id), r]));
        const getV = (v) => this.getMany2OneValue(v).name || "";

        const rows = [["ID", "Create Date", "Created By", "Last Updated Date",
            "Last Updated By", "Date", "User / Author", "Message Type",
            "Subject / Summary", "Message / Note", "Result Type"]];

        for (const m of messages) {
            const a = mMap.get(Number(m.id)) || {};
            rows.push([m.id || "", a.create_date || "", getV(a.create_uid),
                a.write_date || "", getV(a.write_uid), this.getMessageDate(m) || "",
                m.author?.name || "",
                this.messageTypeOptions.find((t) => t.value === m.message_type)?.label || m.message_type || "",
                this.getMessageText(m.subject), this.getMessageText(m.body), "Message"]);
        }
        for (const a of activities) {
            const r = aMap.get(Number(a.id)) || {};
            rows.push([a.id || "", r.create_date || "", getV(r.create_uid),
                r.write_date || "", getV(r.write_uid), a.date_deadline || "",
                getV(a.user_id), getV(a.activity_type_id), a.summary || "",
                this.getMessageText(a.note), "Activity"]);
        }
        const csv = rows.map((r) => r.map((v) => {
            const n = String(v ?? "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").replace(/\n/g, " ");
            return `"${n.replace(/"/g, '""')}"`;
        }).join(",")).join("\r\n");

        const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url; link.download = "advanced_chatter_results.csv";
        document.body.appendChild(link); link.click(); document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },
});

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        const c = this.env.advancedChatterSearch;
        if (c && typeof c.onFiltersChanged === "function") {
            const u = c.onFiltersChanged(() => this.render());
            onWillDestroy(u);
        }
    },
    get filteredMessages() {
        const c = this.env.advancedChatterSearch;
        if (!c) return this.orderedMessages || [];
        return c.filteredMessages || this.orderedMessages || [];
    },
    get activities() {
        const c = this.env.advancedChatterSearch;
        if (!c) return super.activities;
        if (c.isMessageFilterActive) return [];
        if (c.isActivityFilterActive) return c.filteredActivities;
        return super.activities;
    },
});

patch(SearchMessageInput.prototype, {
    setup() {
        super.setup(...arguments);
        this.advancedDropdownState = useState({ expandedGroup: null });
        this.filterDropdownState = useDropdownState();
        const c = this.env.advancedChatterSearch;
        if (c) c.searchMessageInput = this;
        if (c && typeof c.onFiltersChanged === "function") {
            const u = c.onFiltersChanged((close = true) => {
                this.render();
                if (close) this.filterDropdownState.close();
            });
            onWillDestroy(u);
        }
        if (c) onWillDestroy(() => {
            if (c.searchMessageInput === this) c.searchMessageInput = null;
        });
    },
    clear() {
        super.clear();
        const c = this.env.advancedChatterSearch;
        if (c?.clearAdvancedFilters) c.clearAdvancedFilters();
    },
    toggleAdvancedGroup(k) {
        this.advancedDropdownState.expandedGroup =
            this.advancedDropdownState.expandedGroup === k ? null : k;
    },
    onKeywordSync() {
        const c = this.env.advancedChatterSearch;
        if (!c) return;
        setTimeout(() => {
            const v = this.state.searchTerm || "";
            const f = c.advancedFilterState.filters;
            f.keyword = v; f.activeKeyword = ""; f.activeKeywordMode = "";
            f.fieldName = ""; f.fieldLabel = ""; f.fieldValue = ""; f.fieldValueLabel = "";
            c.advancedFilterState.showSuggestions = !!v.trim();
            this.advancedDropdownState.expandedGroup = null;
            if (v.trim()) {
                c._ensureExtracted().then(() => c.notifyFiltersChanged(false));
            }
        }, 0);
    },
    onKeywordFocusSync() {
        const c = this.env.advancedChatterSearch;
        if (c && this.state.searchTerm.trim()) c.advancedFilterState.showSuggestions = true;
    },
    onKeywordBlurSync() {
        const c = this.env.advancedChatterSearch;
        if (!c) return;
        setTimeout(() => {
            c.advancedFilterState.showSuggestions = false;
            this.advancedDropdownState.expandedGroup = null;
        }, 200);
    },
    selectSuggestionAndSync(group, item = null) {
        const c = this.env.advancedChatterSearch;
        if (!c) return;
        c.selectSearchSuggestion(group, item);
    },
    onDateInputClick(ev) {
        const c = this.env.advancedChatterSearch;
        if (c && typeof c.onDateInputClick === "function") {
            c.onDateInputClick(ev);
        }
    },
});

patch(FormCompiler.prototype, {
    setup() {
        super.setup(...arguments);
        const cc = this.compilers.find((c) => c.selector === "chatter");
        if (!cc || cc._advancedChatterPatched) return;
        const orig = cc.fn;
        cc.fn = function (node, params) {
            const r = orig.call(this, node, params);
            if (!r || typeof node?.getAttribute !== "function") return r;
            const xml = Array.from(r.querySelectorAll("t[t-component]"))
                .find((el) => (el.getAttribute("t-component") || "").includes("Chatter"));
            if (!xml) { console.warn(LOG, "Chatter node not found"); return r; }
            let opts = {};
            const oa = node.getAttribute("options");
            if (oa) { try { opts = evaluateExpr(oa) || {}; } catch (e) { console.error(LOG, e); } }
            if ("advance_search" in opts) setAttributes(xml, { advancesearch: !!opts.advance_search });
            if ("advance_filter" in opts) setAttributes(xml, { advancefilter: !!opts.advance_filter });
            return r;
        };
        cc._advancedChatterPatched = true;
    },
});