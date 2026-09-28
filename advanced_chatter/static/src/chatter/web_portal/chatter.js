/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
import { deserializeDate, deserializeDateTime, formatDate, formatDateTime } from "@web/core/l10n/dates";
import { htmlToTextContentInline } from "@mail/utils/common/format";
import { onWillStart, useEffect, useState } from "@odoo/owl";
import { groupBy } from "@web/core/utils/arrays";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { escapeRegExp } from "@web/core/utils/strings";

const ACCESS_CHECK = { model: "res.users", method: "check_advanced_chatter_access" };

const LIMITS = {
    nameList: 200,
    relatedRecords: 200,
    trackingValues: 50,
    recordTextLength: 200,
    fieldMatchItems: 25,
    valueMatchItems: 50,
};

const FIELD_ATTRIBUTES = ["string", "type", "relation", "selection", "searchable"];
const AUDIT_FIELDS = ["id", "create_date", "create_uid", "write_date", "write_uid"];

const DATE_TYPES = new Set(["date", "datetime"]);

const SELECTION_SOURCES = {
    messageTypeOptions: { model: "mail.message", field: "message_type" },
    activityStateOptions: { model: "mail.activity", field: "state" },
};

const NAME_LIST_SOURCES = {
    subtypes: "mail.message.subtype",
    activityTypes: "mail.activity.type",
};

const TRACKING_MODEL = "mail.tracking.value";
const TRACKING_PREFIXES = ["old", "new"];
const TRACKING_COLUMNS = ["char", "text", "integer", "float", "datetime"];
const TRACKING_COLUMNS_BY_TYPE = {
    float: ["float"], monetary: ["float"], integer: ["integer"],
    date: ["datetime"], datetime: ["datetime"],
};

const MESSAGE_SUGGESTION_FIELDS = {
    author_id: "author",
    email_from: "email_from",
    subtype_id: "subtype_id",
    message_type: "message_type",
    subject: "subject",
};
const HTML_MESSAGE_FIELDS = new Set(["subject"]);

const REFERENCE_CODE_FIELDS = ["default_code", "code", "reference", "ref"];
const REFERENCE_MODEL_TYPES = new Set(["many2one", "one2many", "many2many"]);

const RECORD_FILTERS = {
    message: { userId: "author", messageType: "message_type", subtypeId: "subtype_id" },
    activity: {
        activityTypeId: "activity_type_id",
        activityUserId: "user_id",
        activityState: "state",
    },
};

const FILTER_GROUPS = {
    keyword: ["keyword", "activeKeyword", "activeKeywordMode"],
    date: ["dateFrom", "dateTo"],
    field: ["fieldName", "fieldLabel", "fieldValue", "fieldValueLabel"],
};

const KEYWORD_MODE = { MESSAGE: "message", FIELD: "field" };
const MESSAGE_GROUP_KEY = "message";
const FIELD_GROUP_PREFIX = "field:";

const EXPORT_FILENAME = "advanced_chatter_results.csv";
const EXPORT_COLUMNS = [
    ["ID", "id"],
    ["Create Date", "createDate"],
    ["Created By", "createdBy"],
    ["Last Updated Date", "updatedDate"],
    ["Last Updated By", "updatedBy"],
    ["Date", "date"],
    ["User / Author", "user"],
    ["Message Type", "type"],
    ["Subject / Summary", "subject"],
    ["Message / Note", "note"],
    ["Result Type", "resultType"],
];

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

        this.searchableFields = {};
        this.suggestions = [];
        this.fieldValueMessageIds = new Map();
        this.fieldValueActivityIds = new Map();
        this._referenceModelCache = null;

        for (const property of Object.keys(SELECTION_SOURCES)) {
            this[property] = [];
        }

        this._filterChangeListeners = new Set();
        this._fieldDefCache = new Map();
        this._extractedSignature = null;

        this.advancedFilterState = useState({
            showSuggestions: false,
            expandedSuggestionGroup: null,
            isNotification: undefined,
            filters: this._createEmptyFilters(),
            ...Object.fromEntries(Object.keys(NAME_LIST_SOURCES).map((key) => [key, []])),
        });

        onWillStart(() => this._loadInitialData());
        useEffect(
            () => { this._refreshSuggestions(); },
            () => [
                this.threadMessages.length,
                this.conversationActivities.length,
                this.resId,
            ]
        );
    },

    get resModel() {
        return this.props.threadModel || null;
    },

    get resId() {
        return this.props.threadId || null;
    },

    setDateFilter(key, luxonDate) {
        this.advancedFilterState.filters[key] =
            luxonDate && typeof luxonDate.toISODate === "function"
                ? luxonDate.toISODate()
                : "";
        this.notifyDateFilterChanged();
    },

    get dateFromValue() {
        const value = this.advancedFilterState.filters.dateFrom;
        if (!value) return undefined;
        try { return deserializeDate(value); } catch { return undefined; }
    },

    get dateToValue() {
        const value = this.advancedFilterState.filters.dateTo;
        if (!value) return undefined;
        try { return deserializeDate(value); } catch { return undefined; }
    },

    async _safely(callback, fallback = null) {
        try { return await callback(); } catch { return fallback; }
    },

    _isEmpty(value) {
        return [false, null, undefined, ""].includes(value);
    },

    _numericIds(records) {
        return records
            .map((record) => Number(record.id))
            .filter((id) => Number.isFinite(id) && id > 0);
    },

    _selectionLabel(selection, value) {
        const option = (selection || []).find(([key]) => String(key) === String(value));
        return option ? option[1] : String(value);
    },

    _suggestionKey(fieldName, label) {
        return `${fieldName}|${String(label).trim().toLowerCase()}`;
    },

    getMany2OneValue(value) {
        if (Array.isArray(value)) {
            return { id: value[0] || null, name: value[1] || "" };
        }
        if (value && typeof value === "object") {
            return {
                id: value.id || value.res_id || null,
                name: value.display_name || value.name || "",
            };
        }
        return { id: value || null, name: "" };
    },

    _relationName(value) {
        return this.getMany2OneValue(value).name || "";
    },

    _formatDateValue(value, fieldType) {
        const raw = String(value);
        if (fieldType === "date") {
            return formatDate(deserializeDate(raw.slice(0, 10)));
        }
        return formatDateTime(deserializeDateTime(raw));
    },

    _loadFieldDefs(model, fieldNames = [], attributes = FIELD_ATTRIBUTES) {
        const key = JSON.stringify([model, fieldNames, attributes]);
        if (!this._fieldDefCache.has(key)) {
            this._fieldDefCache.set(
                key,
                this._safely(
                    () => this.orm.call(model, "fields_get", [fieldNames, attributes]),
                    {}
                )
            );
        }
        return this._fieldDefCache.get(key);
    },

    _filterKeys(...groups) {
        return groups.flatMap((group) => FILTER_GROUPS[group] || Object.keys(RECORD_FILTERS[group]));
    },

    _createEmptyFilters() {
        return Object.fromEntries(
            this._filterKeys(...Object.keys(FILTER_GROUPS), ...Object.keys(RECORD_FILTERS)).map(
                (key) => [key, ""]
            )
        );
    },

    _resetFilters(...groups) {
        const filters = this.advancedFilterState.filters;
        for (const key of this._filterKeys(...groups)) {
            filters[key] = "";
        }
    },

    clearFieldSelection() {
        this._resetFilters("field");
    },

    _hasActiveFilter(keys) {
        const filters = this.advancedFilterState.filters;
        return keys.some((key) => filters[key]);
    },

    get _messageResultKeys() {
        return ["activeKeyword", ...this._filterKeys("message"), "fieldValueLabel"];
    },

    _matchesRecordFilters(record, group) {
        const filters = this.advancedFilterState.filters;
        return Object.entries(RECORD_FILTERS[group]).every(
            ([key, property]) =>
                !filters[key] ||
                String(this.getMany2OneValue(record[property]).id) === String(filters[key])
        );
    },

    _isInDateRange(date) {
        const { dateFrom, dateTo } = this.advancedFilterState.filters;

        if (!dateFrom && !dateTo) return true;
        if (!date) return false;

        const normalizedDate = String(date).substring(0, 10);
        if (dateFrom && normalizedDate < dateFrom) return false;
        if (dateTo && normalizedDate > dateTo) return false;
        return true;
    },

    async _loadInitialData() {
        this.hasAdvancedChatterAccess = await this.orm.call(
            ACCESS_CHECK.model,
            ACCESS_CHECK.method,
            []
        );
        if (!this.hasAdvancedChatterAccess) return;

        await Promise.all([
            ...Object.entries(SELECTION_SOURCES).map(([property, { model, field }]) =>
                this._loadSelectionOptions(model, field, property)
            ),
            ...Object.entries(NAME_LIST_SOURCES).map(([key, model]) =>
                this._loadNameList(model, key)
            ),
        ]);
        await this.loadAllFields();
    },

    async _loadSelectionOptions(model, fieldName, targetProperty) {
        const defs = await this._loadFieldDefs(model, [fieldName], ["selection"]);
        this[targetProperty] = (defs[fieldName]?.selection || []).map(([value, label]) => ({
            value, label,
        }));
    },

    async _loadNameList(model, stateKey) {
        const records = await this._safely(() =>
            this.orm.searchRead(model, [], ["id", "name"], {
                limit: LIMITS.nameList,
                order: "name asc",
            })
        );
        if (records) {
            this.advancedFilterState[stateKey] = records;
        }
    },

    async loadAllFields() {
        const fields = {};
        await this._collectMessageFields(fields);
        this.searchableFields = fields;
    },

    async _collectMessageFields(fields) {
        const defs = await this._loadFieldDefs(
            "mail.message",
            Object.keys(MESSAGE_SUGGESTION_FIELDS)
        );
        for (const [name, definition] of Object.entries(defs)) {
            fields[name] = this._buildFieldEntry(name, definition, "message");
        }
    },

    _buildFieldEntry(name, definition, source) {
        const { string, type, relation, selection } = definition;
        return { name, string, type, relation, selection, source };
    },

    _currentSignature() {
        return `${this.resId}|${this.threadMessages.length}|${this.conversationActivities.length}`;
    },

    async _refreshSuggestions() {
        const signature = this._currentSignature();
        const hasData = this.threadMessages.length || this.conversationActivities.length;
        if (!hasData || this._extractedSignature === signature) {
            return;
        }
        await this.extractAllSuggestions();
        this._extractedSignature = signature;
        this.notifyFiltersChanged(false);
    },

    async _ensureExtracted() {
        const signature = this._currentSignature();
        if (this._extractedSignature === signature) {
            return;
        }
        await this.extractAllSuggestions();
        this._extractedSignature = signature;
    },

    _createSuggestionCollector() {
        const suggestions = [];
        const seen = new Set();
        const messageIds = new Map();
        const activityIds = new Map();

        const add = (fieldName, displayName, rawValue, messageId = null, activityId = null) => {
            if (!displayName) return;

            const label = String(displayName).trim();
            if (!label || label === "false" || label === "undefined") return;

            const key = this._suggestionKey(fieldName, label);

            if (!seen.has(key)) {
                seen.add(key);
                const field = this.searchableFields[fieldName];
                suggestions.push({
                    fieldName,
                    fieldLabel: field?.string || fieldName,
                    fieldType: field?.type || "",
                    fieldSource: field?.source || "",
                    displayName: label,
                    rawValue,
                });
            }

            if (messageId !== null) {
                const id = Number(messageId);
                if (Number.isFinite(id)) {
                    if (!messageIds.has(key)) messageIds.set(key, new Set());
                    messageIds.get(key).add(id);
                }
            }

            if (activityId !== null) {
                const id = Number(activityId);
                if (Number.isFinite(id)) {
                    if (!activityIds.has(key)) activityIds.set(key, new Set());
                    activityIds.get(key).add(id);
                }
            }
        };

        return { add, suggestions, messageIds, activityIds };
    },

  
    async extractAllSuggestions() {
        const { add, suggestions, messageIds, activityIds } = this._createSuggestionCollector();

        const messages = this.threadMessages;
        const activities = this.conversationActivities;

        this._addMessageFieldSuggestions(messages, add);
        this._addActivitySuggestions(activities, add);
        await this._addTrackingValueSuggestions(messages, add);
        this._addMatchedSelectionLabels(messages, add);
        await this._addMessageBodyReferenceSuggestions(messages, add);

        this.suggestions = suggestions;
        this.fieldValueMessageIds = messageIds;
        this.fieldValueActivityIds = activityIds;
    },

    _addMessageFieldSuggestions(messages, add) {
        for (const message of messages) {
            for (const [fieldName, property] of Object.entries(MESSAGE_SUGGESTION_FIELDS)) {
                const value = HTML_MESSAGE_FIELDS.has(fieldName)
                    ? this.getMessageText(message[property])
                    : message[property];
                this._addFieldSuggestion(this.searchableFields[fieldName], value, add, [message.id]);
            }
        }
    },

    _addActivitySuggestions(activities, add) {
        if (!activities?.length) return;

        const fieldDefs = {
            activity_type_id: { string: "Activity Type",     type: "many2one", relation: "mail.activity.type" },
            summary:          { string: "Activity Summary",  type: "char" },
            user_id:          { string: "Activity User",     type: "many2one", relation: "res.users" },
            date_deadline:    { string: "Activity Deadline", type: "date" },
            state:            { string: "Activity Status",   type: "selection" },
        };

        const stateSelection = (this.activityStateOptions || []).map((o) => [o.value, o.label]);

        for (const [name, def] of Object.entries(fieldDefs)) {
            if (!this.searchableFields[name]) {
                this.searchableFields[name] = {
                    name,
                    relation: null,
                    selection: name === "state" ? stateSelection : null,
                    source: "activity",
                    ...def,
                };
            }
        }

        for (const activity of activities) {
            for (const name of Object.keys(fieldDefs)) {
                const value = activity[name];
                if (this._isEmpty(value)) continue;
                this._addFieldSuggestion(
                    this.searchableFields[name],
                    value,
                    add,
                    [],
                    [activity.id]
                );
            }
        }
    },

    _addFieldSuggestion(field, value, add, messageIds = [null], activityIds = []) {
        if (!field || this._isEmpty(value)) return;

        const formatted = this._formatFieldValue(field, value);
        if (!formatted) return;

        if (activityIds.length) {
            for (const activityId of activityIds) {
                add(field.name, formatted[0], formatted[1], null, activityId);
            }
            return;
        }

        for (const messageId of messageIds) {
            add(field.name, formatted[0], formatted[1], messageId);
        }
    },

    _formatFieldValue(field, value) {
        switch (field.type) {
            case "many2one": {
                const { id, name } = this.getMany2OneValue(value);
                return id ? [name, id] : null;
            }
            case "selection":
                return [this._selectionLabel(field.selection, value), value];
            case "date":
            case "datetime":
                return [this._formatDateValue(value, field.type), value];
            case "text":
            case "html": {
                const text = this.getMessageText(value);
                return text && text.length <= LIMITS.recordTextLength ? [text, value] : null;
            }
            default:
                return [String(value), value];
        }
    },

    get _trackingReadFields() {
        return [
            "mail_message_id",
            "field_id",
            ...TRACKING_PREFIXES.flatMap((prefix) =>
                TRACKING_COLUMNS.map((column) => `${prefix}_value_${column}`)
            ),
        ];
    },

    async _addTrackingValueSuggestions(messages, add) {
        const messageIds = this._numericIds(messages);
        if (!messageIds.length) return;

        await this._safely(async () => {
            const trackingValues = await this.orm.searchRead(
                TRACKING_MODEL,
                [["mail_message_id", "in", messageIds]],
                this._trackingReadFields,
                { limit: LIMITS.trackingValues }
            );
            const fieldDefs = await this._loadTrackingFieldDefs(trackingValues);

            for (const tracking of trackingValues) {
                const messageId = Number(this.getMany2OneValue(tracking.mail_message_id).id);
                const definition = fieldDefs.get(
                    Number(this.getMany2OneValue(tracking.field_id).id)
                );
                if (!messageId || !definition) continue;

                if (!this.searchableFields[definition.name]) {
                    this.searchableFields[definition.name] = {
                        name: definition.name,
                        string: definition.field_description || definition.name,
                        type: definition.ttype || "char",
                        relation: definition.relation || null,
                        selection: definition.selection || null,
                        source: "tracking",
                    };
                }
                const field = this.searchableFields[definition.name];

                for (const prefix of TRACKING_PREFIXES) {
                    const rawValue = this._readTrackingValue(tracking, prefix, field.type);
                    if (this._isEmpty(rawValue)) continue;
                    add(field.name, this._trackingValueLabel(field, rawValue), rawValue, messageId);
                }
            }
        });
    },

    _trackingValueLabel(field, rawValue) {
        if (DATE_TYPES.has(field.type)) {
            return this._formatDateValue(rawValue, field.type);
        }
        if (field.type === "selection") {
            return this._selectionLabel(field.selection, rawValue);
        }
        return String(rawValue);
    },

    async _loadTrackingFieldDefs(trackingValues) {
        const fieldIds = [
            ...new Set(
                trackingValues
                    .map((tracking) => this.getMany2OneValue(tracking.field_id).id)
                    .filter(Boolean)
                    .map(Number)
            ),
        ];
        if (!fieldIds.length) return new Map();

        const definitions = await this.orm.searchRead(
            "ir.model.fields",
            [["id", "in", fieldIds]],
            ["id", "name", "field_description", "ttype", "relation", "model"],
            { limit: fieldIds.length }
        );

        const selectionNamesByModel = new Map();
        for (const def of definitions) {
            if (def.ttype === "selection" && def.model) {
                if (!selectionNamesByModel.has(def.model)) {
                    selectionNamesByModel.set(def.model, []);
                }
                selectionNamesByModel.get(def.model).push(def.name);
            }
        }

        const selectionByKey = new Map();
        for (const [model, names] of selectionNamesByModel) {
            const defs = await this._loadFieldDefs(model, names, ["selection"]);
            for (const name of names) {
                selectionByKey.set(`${model}|${name}`, defs?.[name]?.selection || null);
            }
        }

        return new Map(
            definitions.map((def) => [
                Number(def.id),
                {
                    ...def,
                    selection: selectionByKey.get(`${def.model}|${def.name}`) || null,
                },
            ])
        );
    },

    _readTrackingValue(tracking, prefix, fieldType) {
        return (TRACKING_COLUMNS_BY_TYPE[fieldType] || TRACKING_COLUMNS)
            .map((column) => tracking[`${prefix}_value_${column}`])
            .find((value) => !this._isEmpty(value));
    },

    _addMatchedSelectionLabels(messages, add) {
        const allText = messages.map((message) => this._getMessageSearchText(message)).join(" ");

        for (const [fieldName, field] of Object.entries(this.searchableFields)) {
            if (field.type !== "selection" || !Array.isArray(field.selection)) continue;
            for (const [value, label] of field.selection) {
                const isUsefulLabel =
                    typeof label === "string" &&
                    label &&
                    label.toLowerCase() !== String(value).toLowerCase();
                if (isUsefulLabel && allText.includes(label.toLowerCase())) {
                    add(fieldName, label, value);
                }
            }
        }
    },

    async _loadReferenceModels() {
        if (this._referenceModelCache) return this._referenceModelCache;

        const result = [];
        if (!this.resModel || !this.resId) {
            this._referenceModelCache = result;
            return result;
        }

        const parentDefs = await this._loadFieldDefs(this.resModel);
        const relatedModels = new Set();
        for (const def of Object.values(parentDefs || {})) {
            if (def.relation && REFERENCE_MODEL_TYPES.has(def.type)) {
                relatedModels.add(def.relation);
            }
        }
        if (!relatedModels.size) {
            this._referenceModelCache = result;
            return result;
        }

        const modelList = [...relatedModels];

        const codeFieldDefs = await this._safely(() =>
            this.orm.searchRead(
                "ir.model.fields",
                [
                    ["model", "in", modelList],
                    ["ttype", "==", "char"],
                    ["store", "==", true],
                    ["name", "in", REFERENCE_CODE_FIELDS],
                ],
                ["model", "name"]
            )
        , []);

        const modelInfos = await this._safely(() =>
            this.orm.searchRead(
                "ir.model",
                [["model", "in", modelList]],
                ["model", "name"]
            )
        , []);
        const labelByModel = new Map(modelInfos.map((m) => [m.model, m.name]));

        for (const cf of codeFieldDefs) {
            result.push({
                model: cf.model,
                codeField: cf.name,
                label: labelByModel.get(cf.model) || cf.model,
            });
        }

        this._referenceModelCache = result;
        return result;
    },

    async _addMessageBodyReferenceSuggestions(messages, add) {
        const candidates = await this._loadReferenceModels();
        if (!candidates.length) return;

        const referenceRegex = /\[([A-Z0-9][A-Z0-9_\-\.]*)\]\s*([A-Za-z0-9][^:<\n\r&\[\]]*)/g;
        const references = new Map();

        for (const message of messages) {
            const text = [message.subject, message.body]
                .map((v) => this.getMessageText(v))
                .join(" ");
            if (!text) continue;

            referenceRegex.lastIndex = 0;
            let match;
            while ((match = referenceRegex.exec(text)) !== null) {
                const code = match[1];
                const name = match[2].trim().replace(/[\s.,;:!?]+$/, "");
                if (!name || name.length < 2) continue;
                if (!references.has(code)) {
                    references.set(code, {
                        code,
                        label: `[${code}] ${name}`,
                        messageId: message.id,
                    });
                }
            }
        }
        if (!references.size) return;

        for (const ref of references.values()) {
            for (const cand of candidates) {
                const found = await this._safely(() =>
                    this.orm.searchRead(
                        cand.model,
                        [[cand.codeField, "=", ref.code]],
                        ["id"],
                        { limit: 1 }
                    )
                , []);
                if (!found?.length) continue;
                
                const fieldName = `__ref_${cand.model}`;
                if (!this.searchableFields[fieldName]) {
                    this.searchableFields[fieldName] = {
                        name: fieldName,
                        string: cand.label,
                        type: "char",
                        relation: cand.model,
                        selection: null,
                        source: "message",
                    };
                }
                add(fieldName, ref.label, ref.label, ref.messageId);
                break;
            }
        }
    },

    onFiltersChanged(callback) {
        this._filterChangeListeners.add(callback);
        return () => this._filterChangeListeners.delete(callback);
    },

    notifyFiltersChanged(shouldAttemptClose = true) {
        for (const listener of this._filterChangeListeners) {
            listener(shouldAttemptClose);
        }
    },

    notifyDateFilterChanged() {
        const { dateFrom, dateTo } = this.advancedFilterState.filters;
        this.notifyFiltersChanged(Boolean(dateFrom && dateTo));
    },

    get isSearchFilterActive() {
        return this.advancedFilterState.isNotification !== undefined;
    },

    get showActivityFilters() {
        return !this.isSearchFilterActive;
    },

    onSearchFilterChanged(isNotification) {
        this.advancedFilterState.isNotification = isNotification;
        if (!this.showActivityFilters) {
            this._resetFilters("activity");
        }
        this.notifyFiltersChanged(false);
    },

    onMessageFilterChanged() {
        this._resetFilters("activity");
        this.notifyFiltersChanged();
    },

    onActivityFilterChanged() {
        this._resetFilters("keyword", "message", "field");
        this.notifyFiltersChanged();
    },

    get threadMessages() {
        return this.state.thread?.messages || [];
    },

    get searchFilterMessages() {
        return this.threadMessages.filter((message) => this._matchesSearchFilter(message));
    },

    get conversationActivities() {
        return this.state.thread?.activities || [];
    },

    get conversationAuthors() {
        return this._uniqueMany2OneList(this.searchFilterMessages, "author");
    },

    get conversationActivityTypes() {
        return this._uniqueMany2OneList(this.conversationActivities, "activity_type_id");
    },

    get conversationActivityUsers() {
        return this._uniqueMany2OneList(this.conversationActivities, "user_id");
    },

    get conversationMessageTypes() {
        return this._filterUsedOptions(
            this.messageTypeOptions,
            this.searchFilterMessages.map((message) => message.message_type)
        );
    },

    get conversationSubtypes() {
        return this._filterUsedOptions(
            this.advancedFilterState.subtypes,
            this.searchFilterMessages.map((message) =>
                Number(this.getMany2OneValue(message.subtype_id).id)
            ),
            "id"
        );
    },

    get conversationActivityStates() {
        return this._filterUsedOptions(
            this.activityStateOptions,
            this.conversationActivities.map((activity) => activity.state)
        );
    },

    _filterUsedOptions(options, usedValues, key = "value") {
        const used = new Set(usedValues);
        return options.filter((option) => used.has(option[key]));
    },

    _uniqueMany2OneList(records, property) {
        const items = new Map();
        for (const record of records) {
            const { id, name } = this.getMany2OneValue(record[property]);
            if (id && !items.has(Number(id))) {
                items.set(Number(id), { id: Number(id), name });
            }
        }
        return [...items.values()].sort((a, b) => a.name.localeCompare(b.name));
    },

    get isActivityFilterActive() {
        return this._hasActiveFilter(this._filterKeys("activity"));
    },

    get isMessageFilterActive() {
        return this._hasActiveFilter(this._messageResultKeys);
    },

    get activeAdvancedFilterCount() {
        const filters = this.advancedFilterState.filters;
        const dateActive = Boolean(filters.dateFrom || filters.dateTo);
        const keys = [...this._filterKeys("message", "activity"), "fieldValueLabel"];
        const hasMessageKeyword =
            filters.activeKeywordMode === KEYWORD_MODE.MESSAGE && filters.activeKeyword;
        return (
            keys.filter((key) => filters[key]).length +
            Number(Boolean(hasMessageKeyword)) +
            Number(dateActive)
        );
    },

    _activeFieldMatchActivityIds() {
        const filters = this.advancedFilterState.filters;
        if (
            filters.activeKeywordMode !== KEYWORD_MODE.FIELD ||
            !filters.fieldName
        ) {
            return null;
        }
        const key = this._suggestionKey(filters.fieldName, filters.fieldValueLabel);
        return this.fieldValueActivityIds.get(key) || null;
    },

    get activities() {
        if (this.isSearchFilterActive) {
            return [];
        }

        const activityIds = this._activeFieldMatchActivityIds();
        if (activityIds?.size) {
            return this.conversationActivities.filter(
                (activity) =>
                    activityIds.has(Number(activity.id)) &&
                    this._isInDateRange(this.getActivityDate(activity)) &&
                    this._matchesRecordFilters(activity, "activity")
            );
        }

        if (this.isMessageFilterActive) {
            return [];
        }

        const activities = this.conversationActivities;

        if (!this._hasActiveFilter(this._filterKeys("date", "activity"))) {
            return activities;
        }

        return activities.filter(
            (activity) =>
                this._isInDateRange(this.getActivityDate(activity)) &&
                this._matchesRecordFilters(activity, "activity")
        );
    },

    get filteredMessages() {
        if (this._activeFieldMatchActivityIds()?.size) {
            return [];
        }

        if (this.isActivityFilterActive) return [];

        const hasFilter =
            this.isSearchFilterActive ||
            this._hasActiveFilter([
                ...this._messageResultKeys,
                ...this._filterKeys("date"),
            ]);

        if (!hasFilter) return this.threadMessages;

        return this._applyStructuredFilters(
            this._applyFieldValueFilter(
                this._applyKeywordFilter(this.threadMessages)
            )
        );
    },

    _applyKeywordFilter(messages) {
        const { activeKeyword, activeKeywordMode } = this.advancedFilterState.filters;
        const keyword = (activeKeyword || "").trim().toLowerCase();
        if (!keyword || activeKeywordMode !== KEYWORD_MODE.MESSAGE) {
            return messages;
        }
        return messages.filter((message) => this._getMessageSearchText(message).includes(keyword));
    },

    _applyFieldValueFilter(messages) {
        const {
            activeKeywordMode,
            fieldName,
            fieldValueLabel,
        } = this.advancedFilterState.filters;

        if (
            activeKeywordMode !== KEYWORD_MODE.FIELD ||
            !fieldName ||
            !fieldValueLabel
        ) {
            return messages;
        }

        const key = this._suggestionKey(fieldName, fieldValueLabel);
        const messageIds = this.fieldValueMessageIds.get(key);

        if (messageIds?.size) {
            return messages.filter((message) => messageIds.has(Number(message.id)));
        }

        const needle = String(fieldValueLabel).trim().toLowerCase();
        if (!needle) {
            return [];
        }

        const exactMatches = messages.filter((message) =>
            this._getMessageSearchText(message).includes(needle)
        );
        if (exactMatches.length) {
            return exactMatches;
        }

        const primary = needle.split(/\s*[\(\[].*$/)[0].trim();
        if (primary && primary !== needle) {
            return messages.filter((message) =>
                this._getMessageSearchText(message).includes(primary)
            );
        }

        return [];
    },

    _matchesSearchFilter(message) {
        const { isNotification } = this.advancedFilterState;
        return (
            isNotification === undefined ||
            (message.message_type === "notification") === isNotification
        );
    },

    _applyStructuredFilters(messages) {
        return messages.filter(
            (message) =>
                this._matchesSearchFilter(message) &&
                this._isInDateRange(this.getMessageDate(message)) &&
                this._matchesRecordFilters(message, "message")
        );
    },

    get currentSearchKeyword() {
        return this.searchMessageInput?.state?.searchTerm || "";
    },

    get searchSuggestionGroups() {
        const term = this.currentSearchKeyword.trim().toLowerCase();
        if (!term) return [];

        const regex = new RegExp(`(^|[\\s\\W_])${escapeRegExp(term)}`, "i");

        const fieldGroups = Object.entries(groupBy(this.suggestions, "fieldName"))
            .map(([fieldName, items]) => this._buildFieldSuggestionGroup(fieldName, items, term, regex))
            .filter(Boolean)
            .sort((a, b) => Number(a._fieldMatched) - Number(b._fieldMatched));

        return [
            { key: MESSAGE_GROUP_KEY, label: "Message", items: [], expandable: false },
            ...fieldGroups,
        ];
    },

    _matchSuggestionValues(items, term, regex) {
        return items.filter((item) => {
            const text = item.displayName.toLowerCase();
            return regex.test(text) || text === term;
        });
    },

    _buildFieldSuggestionGroup(fieldName, items, term, regex) {
        const field = this.searchableFields[fieldName];
        const label = field?.string || fieldName;
        const isFieldMatch = [label, fieldName].some((name) => name.toLowerCase() === term);

        let matches;
        let limit;
        if (isFieldMatch) {
            matches = [...items].sort((a, b) => a.displayName.localeCompare(b.displayName));
            limit = LIMITS.fieldMatchItems;
        } else {
            matches = this._matchSuggestionValues(items, term, regex);
            if (!matches.length) return null;
            const rank = (item) => {
                const text = item.displayName.toLowerCase();
                return text === term ? 0 : text.startsWith(term) ? 1 : 2;
            };
            matches.sort((a, b) => rank(a) - rank(b));
            limit = LIMITS.valueMatchItems;
        }

        return {
            key: `${FIELD_GROUP_PREFIX}${fieldName}`,
            label,
            fieldName,
            fieldType: field?.type || "",
            items: matches.slice(0, limit),
            expandable: matches.length > 1,
            _fieldMatched: isFieldMatch,
        };
    },

    clearKeywordSearch() {
        Object.assign(this.advancedFilterState.filters, this._createEmptyFilters());
        this._closeSuggestionsAndNotify();
    },

    clearAdvancedFilters() {
        this.clearKeywordSearch();
    },

    toggleSuggestionGroup(key) {
        const state = this.advancedFilterState;
        state.expandedSuggestionGroup = state.expandedSuggestionGroup === key ? null : key;
    },

    selectSearchSuggestion(group, item = null) {
        if (!group?.key) {
            return;
        }

        if (group.key.startsWith(FIELD_GROUP_PREFIX)) {
            const selectedItem =
                item ||
                (group.items?.length === 1 ? group.items[0] : null);

            if (selectedItem) {
                this.selectFieldSuggestion(
                    group.fieldName,
                    selectedItem,
                    group.label
                );
            }
        } else if (group.key === MESSAGE_GROUP_KEY) {
            this.selectMessageSuggestion();
        }
    },

    selectFieldSuggestion(fieldName, item, fieldLabel) {
        Object.assign(this.advancedFilterState.filters, {
            keyword: item.displayName,
            activeKeyword: item.displayName,
            activeKeywordMode: KEYWORD_MODE.FIELD,
            fieldName,
            fieldLabel,
            fieldValue: item.rawValue,
            fieldValueLabel: item.displayName,
        });
        this._resetFilters("message", "activity");
        this._closeSuggestionsAndNotify();
    },

    selectMessageSuggestion() {
        const filters = this.advancedFilterState.filters;
        const keyword = filters.keyword.trim();
        if (!keyword) return;
        filters.activeKeyword = keyword;
        filters.activeKeywordMode = KEYWORD_MODE.MESSAGE;
        this.clearFieldSelection();
        this._closeSuggestionsAndNotify();
    },

    _closeSuggestionsAndNotify() {
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.notifyFiltersChanged();
    },

    _getMessageSearchText(message) {
        return [message.subject, message.body]
            .map((value) => this.getMessageText(value))
            .join(" ")
            .toLowerCase();
    },

    getActivityDate(activity) {
        return activity?.date_deadline ? String(activity.date_deadline).substring(0, 10) : null;
    },

    getMessageDate(message) {
        const date = message?.date;
        if (!date) return null;
        try {
            if (typeof date.toISODate === "function") {
                return date.toISODate();
            }
            return typeof date === "string" ? date.substring(0, 10) : null;
        } catch {
            return null;
        }
    },

    getMessageText(value) {
        return value ? htmlToTextContentInline(String(value)).trim() : "";
    },

    async exportAdvancedResults() {
        const messages = this.filteredMessages || [];
        const activities = this.activities || [];
        if (!messages.length && !activities.length) return;

        const [messageAudit, activityAudit] = await this._fetchAuditData(messages, activities);
        const records = [
            ...messages.map((m) => this._messageExportRecord(m, messageAudit.get(Number(m.id)))),
            ...activities.map((a) => this._activityExportRecord(a, activityAudit.get(Number(a.id)))),
        ];
        const rows = [
            EXPORT_COLUMNS.map(([header]) => header),
            ...records.map((record) => EXPORT_COLUMNS.map(([, key]) => record[key])),
        ];
        this._downloadCsv(rows, EXPORT_FILENAME);
    },

    async _fetchAuditData(messages, activities) {
        return this._safely(
            () =>
                Promise.all([
                    this._fetchAuditById("mail.message", messages),
                    this._fetchAuditById("mail.activity", activities),
                ]),
            [new Map(), new Map()]
        );
    },

    async _fetchAuditById(model, records) {
        const ids = this._numericIds(records);
        if (!ids.length) return new Map();
        const audits = await this.orm.searchRead(model, [["id", "in", ids]], AUDIT_FIELDS, {
            limit: ids.length,
        });
        return new Map(audits.map((audit) => [Number(audit.id), audit]));
    },

    _auditInfo(audit = {}) {
        return {
            createDate: audit.create_date ? this._formatDateValue(audit.create_date, "datetime") : "",
            createdBy: this._relationName(audit.create_uid),
            updatedDate: audit.write_date ? this._formatDateValue(audit.write_date, "datetime") : "",
            updatedBy: this._relationName(audit.write_uid),
        };
    },

    _messageExportRecord(message, audit) {
        const typeOption = this.messageTypeOptions.find((t) => t.value === message.message_type);
        const date = this.getMessageDate(message);
        return {
            id: message.id || "",
            ...this._auditInfo(audit),
            date: date ? this._formatDateValue(date, "date") : "",
            user: message.author?.name || "",
            type: typeOption?.label || message.message_type || "",
            subject: this.getMessageText(message.subject),
            note: this.getMessageText(message.body),
            resultType: "Message",
        };
    },

    _activityExportRecord(activity, audit) {
        return {
            id: activity.id || "",
            ...this._auditInfo(audit),
            date: activity.date_deadline ? this._formatDateValue(activity.date_deadline, "date") : "",
            user: this._relationName(activity.user_id),
            type: this._relationName(activity.activity_type_id),
            subject: activity.summary || "",
            note: this.getMessageText(activity.note),
            resultType: "Activity",
        };
    },

    _downloadCsv(rows, filename) {
        const quote = (value) =>
            `"${String(value ?? "")
                .replace(/\r\n|\r|\n/g, " ")
                .replace(/"/g, '""')}"`;
        const csv = rows.map((row) => row.map(quote).join(",")).join("\r\n");

        const url = URL.createObjectURL(
            new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" })
        );
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    },
});