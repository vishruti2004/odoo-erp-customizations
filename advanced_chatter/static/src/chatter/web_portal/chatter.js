/** @odoo-module **/

import { Chatter } from "@mail/chatter/web_portal/chatter";
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
    trackingValues: 3000,
    recordTextLength: 200,
    fieldMatchItems: 25,
    valueMatchItems: 15,
};

const FIELD_ATTRIBUTES = ["string", "type", "relation", "selection", "searchable"];
const AUDIT_FIELDS = ["id", "create_date", "create_uid", "write_date", "write_uid"];
const SYSTEM_FIELDS = [...AUDIT_FIELDS, "__last_update", "display_name"];
const EXCLUDED_RECORD_FIELDS = new Set([...SYSTEM_FIELDS, "access_token", "message_ids"]);
const EXCLUDED_RELATED_FIELDS = new Set(SYSTEM_FIELDS);

const SEARCHABLE_FIELD_TYPES = new Set([
    "char",
    "text",
    "many2one",
    "selection",
    "integer",
    "float",
    "monetary",
    "date",
    "datetime",
    "html",
    "one2many",
    "many2many",
]);
const X2MANY_TYPES = new Set(["one2many", "many2many"]);

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
    float: ["float"],
    monetary: ["float"],
    integer: ["integer"],
    date: ["datetime"],
    datetime: ["datetime"],
};

const MESSAGE_SUGGESTION_FIELDS = {
    author_id: "author",
    email_from: "email_from",
    subtype_id: "subtype_id",
    message_type: "message_type",
    subject: "subject",
};

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
        for (const property of Object.keys(SELECTION_SOURCES)) {
            this[property] = [];
        }

        this._filterChangeListeners = new Set();
        this._fieldDefCache = new Map();
        this._extractedSignature = null;

        this.advancedFilterState = useState({
            showSuggestions: false,
            expandedSuggestionGroup: null,
            filters: this.createEmptyFilters(),
            ...Object.fromEntries(Object.keys(NAME_LIST_SOURCES).map((key) => [key, []])),
        });

        onWillStart(() => this._loadInitialData());
        useEffect(
            () => {
                this._refreshSuggestions();
            },
            () => [this.threadMessages.length, this.resId]
        );
    },

    get resModel() {
        return this.props.resModel || this.props.record?.resModel || this.props.threadModel;
    },

    get resId() {
        return this.props.resId || this.props.record?.resId || this.props.threadId;
    },

    async _safely(callback, fallback = null) {
        try {
            return await callback();
        } catch {
            return fallback;
        }
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

    createEmptyFilters() {
        return Object.fromEntries(
            this._filterKeys(...Object.keys(FILTER_GROUPS), ...Object.keys(RECORD_FILTERS)).map(
                (key) => [key, ""]
            )
        );
    },

    _resetFilters(filters, ...groups) {
        for (const key of this._filterKeys(...groups)) {
            filters[key] = "";
        }
    },

    clearFieldSelection(filters) {
        this._resetFilters(filters, "field");
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
        return !(dateFrom && (!date || date < dateFrom)) && !(dateTo && (!date || date > dateTo));
    },

    async _loadInitialData() {
        this.hasAdvancedChatterAccess = await this.orm.call(
            ACCESS_CHECK.model,
            ACCESS_CHECK.method,
            []
        );
        if (!this.hasAdvancedChatterAccess) {
            return;
        }
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
            value,
            label,
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
        if (this.resModel) {
            await this._collectRecordFields(fields);
        }
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

    async _collectRecordFields(fields) {
        const defs = await this._loadFieldDefs(this.resModel);
        for (const [name, definition] of Object.entries(defs)) {
            const isUsable =
                !EXCLUDED_RECORD_FIELDS.has(name) &&
                SEARCHABLE_FIELD_TYPES.has(definition.type) &&
                definition.searchable !== false &&
                !fields[name];
            if (isUsable) {
                fields[name] = this._buildFieldEntry(name, definition, "record");
            }
        }
    },

    _buildFieldEntry(name, definition, source) {
        const { string, type, relation, selection } = definition;
        return { name, string, type, relation, selection, source };
    },

    _currentSignature() {
        return `${this.resId}|${this.threadMessages.length}`;
    },

    async _refreshSuggestions() {
        const signature = this._currentSignature();
        if (!this.threadMessages.length || this._extractedSignature === signature) {
            return;
        }
        await this.extractAllSuggestions();
        this._extractedSignature = signature;
        this.notifyFiltersChanged(false);
    },

    async _ensureExtracted() {
        const signature = this._currentSignature();
        if (this._extractedSignature === signature && this.suggestions.length) {
            return;
        }
        await this.extractAllSuggestions();
        this._extractedSignature = signature;
    },

    _createSuggestionCollector() {
        const suggestions = [];
        const seen = new Set();
        const messageIds = new Map();

        const add = (fieldName, displayName, rawValue, messageId = null) => {
            if (!displayName) {
                return;
            }
            const label = String(displayName).trim();
            if (!label || label === "false" || label === "undefined") {
                return;
            }

            const key = this._suggestionKey(fieldName, label);
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

            const id = Number(messageId);
            if (messageId !== null && Number.isFinite(id)) {
                if (!messageIds.has(key)) {
                    messageIds.set(key, new Set());
                }
                messageIds.get(key).add(id);
            }
        };

        return { add, suggestions, messageIds };
    },

    async extractAllSuggestions() {
        const { add, suggestions, messageIds } = this._createSuggestionCollector();
        const messages = this.threadMessages;

        this._addMessageFieldSuggestions(messages, add);
        await this._addRecordFieldSuggestions(add);
        await this._addTrackingValueSuggestions(messages, add);
        this._addMatchedSelectionLabels(messages, add);

        this.suggestions = suggestions;
        this.fieldValueMessageIds = messageIds;
    },

    _addMessageFieldSuggestions(messages, add) {
        for (const message of messages) {
            for (const [fieldName, property] of Object.entries(MESSAGE_SUGGESTION_FIELDS)) {
                this._addFieldSuggestion(
                    this.searchableFields[fieldName],
                    message[property],
                    add,
                    message.id
                );
            }
        }
    },

    async _addRecordFieldSuggestions(add) {
        if (!this.resModel || !this.resId) {
            return;
        }
        const fields = Object.values(this.searchableFields).filter((f) => f.source === "record");
        const [record] = await this._safely(
            () =>
                this.orm.read(
                    this.resModel,
                    [this.resId],
                    fields.map((f) => f.name)
                ),
            []
        );
        if (!record) {
            return;
        }

        const isX2many = (field) => X2MANY_TYPES.has(field.type);
        for (const field of fields.filter((f) => !isX2many(f))) {
            this._addFieldSuggestion(field, record[field.name], add);
        }
        for (const field of fields.filter(isX2many)) {
            await this._addRelatedFieldSuggestions(field, record[field.name], add);
        }
    },

    _addFieldSuggestion(field, value, add, messageId = null) {
        if (!field || this._isEmpty(value)) {
            return;
        }
        const formatted = this._formatFieldValue(field, value);
        if (formatted) {
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
            case "char":
                return [this.getMessageText(value), value];
            case "text":
            case "html": {
                const text = this.getMessageText(value);
                return text && text.length <= LIMITS.recordTextLength ? [text, value] : null;
            }
            default:
                return [String(value), value];
        }
    },

    async _addRelatedFieldSuggestions(field, ids, add) {
        if (!field.relation || !Array.isArray(ids) || !ids.length) {
            return;
        }
        await this._safely(async () => {
            const defs = await this._loadFieldDefs(field.relation);
            const usable = Object.entries(defs).filter(
                ([name]) => !EXCLUDED_RELATED_FIELDS.has(name)
            );
            const namesOfType = (...types) =>
                usable.filter(([, def]) => types.includes(def.type)).map(([name]) => name);
            const many2oneNames = namesOfType("many2one");
            const plainNames = namesOfType("char", "selection");
            if (!many2oneNames.length && !plainNames.length) {
                return;
            }

            const records = await this.orm.read(
                field.relation,
                ids.slice(0, LIMITS.relatedRecords),
                [...many2oneNames, ...plainNames]
            );
            for (const record of records) {
                for (const name of many2oneNames) {
                    const [id, label] = Array.isArray(record[name]) ? record[name] : [];
                    if (id) {
                        add(name, label, id);
                    }
                }
                for (const name of plainNames) {
                    const value = record[name];
                    if (value) {
                        const { type, selection } = defs[name];
                        add(
                            name,
                            type === "selection"
                                ? this._selectionLabel(selection, value)
                                : String(value),
                            value
                        );
                    }
                }
            }
        });
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
        if (!messageIds.length) {
            return;
        }
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
                const field = this.searchableFields[definition?.name];
                if (!messageId || !field) {
                    continue;
                }
                for (const prefix of TRACKING_PREFIXES) {
                    const rawValue = this._readTrackingValue(tracking, prefix, field.type);
                    if (this._isEmpty(rawValue)) {
                        continue;
                    }
                    add(
                        field.name,
                        field.type === "selection"
                            ? this._selectionLabel(field.selection, rawValue)
                            : String(rawValue),
                        rawValue,
                        messageId
                    );
                }
            }
        });
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
        if (!fieldIds.length) {
            return new Map();
        }
        const definitions = await this.orm.searchRead(
            "ir.model.fields",
            [["id", "in", fieldIds]],
            ["id", "name"],
            { limit: fieldIds.length }
        );
        return new Map(definitions.map((definition) => [Number(definition.id), definition]));
    },

    _readTrackingValue(tracking, prefix, fieldType) {
        return (TRACKING_COLUMNS_BY_TYPE[fieldType] || TRACKING_COLUMNS)
            .map((column) => tracking[`${prefix}_value_${column}`])
            .find((value) => !this._isEmpty(value));
    },

    _addMatchedSelectionLabels(messages, add) {
        const allText = messages.map((message) => this._getMessageSearchText(message)).join(" ");

        for (const [fieldName, field] of Object.entries(this.searchableFields)) {
            if (field.type !== "selection" || !Array.isArray(field.selection)) {
                continue;
            }
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

    onMessageFilterChanged() {
        this._resetFilters(this.advancedFilterState.filters, "activity");
        this.notifyFiltersChanged();
    },

    onActivityFilterChanged() {
        this._resetFilters(this.advancedFilterState.filters, "keyword", "message", "field");
        this.notifyFiltersChanged();
    },

    get threadMessages() {
        return this.state.thread?.messages || [];
    },

    get conversationActivities() {
        return this.state.thread?.activities || [];
    },

    get conversationAuthors() {
        return this._uniqueMany2OneList(this.threadMessages, "author");
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
            this.threadMessages.map((message) => message.message_type)
        );
    },

    get conversationSubtypes() {
        return this._filterUsedOptions(
            this.advancedFilterState.subtypes,
            this.threadMessages.map((message) =>
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
        const keys = [...this._filterKeys("date", "message", "activity"), "fieldValueLabel"];
        const hasMessageKeyword =
            filters.activeKeywordMode === KEYWORD_MODE.MESSAGE && filters.activeKeyword;
        return keys.filter((key) => filters[key]).length + Number(Boolean(hasMessageKeyword));
    },

    get activities() {
        if (this.isMessageFilterActive) {
            return [];
        }
        const activities = this.conversationActivities;
        if (!this._hasActiveFilter(this._filterKeys("date", "activity"))) {
            return activities;
        }
        return activities.filter(
            (activity) =>
                this._isInDateRange(activity.date_deadline || "") &&
                this._matchesRecordFilters(activity, "activity")
        );
    },

    get filteredMessages() {
        const filters = this.advancedFilterState.filters;
        if (this.isActivityFilterActive) {
            return [];
        }
        if (!this._hasActiveFilter([...this._messageResultKeys, ...this._filterKeys("date")])) {
            return this.threadMessages;
        }
        const predicates = [
            this._keywordPredicate(filters),
            this._fieldValuePredicate(filters),
            (message) =>
                this._isInDateRange(this.getMessageDate(message)) &&
                this._matchesRecordFilters(message, "message"),
        ].filter(Boolean);
        return this.threadMessages.filter((message) => predicates.every((test) => test(message)));
    },

    _keywordPredicate(filters) {
        const keyword = (filters.activeKeyword || "").trim().toLowerCase();
        if (!keyword || filters.activeKeywordMode !== KEYWORD_MODE.MESSAGE) {
            return null;
        }
        return (message) => this._getMessageSearchText(message).includes(keyword);
    },

    _fieldValuePredicate(filters) {
        const { activeKeywordMode, fieldName, fieldValueLabel } = filters;
        if (activeKeywordMode !== KEYWORD_MODE.FIELD || !fieldName || !fieldValueLabel) {
            return null;
        }
        const value = fieldValueLabel.trim().toLowerCase();
        const messageIds = this.fieldValueMessageIds.get(this._suggestionKey(fieldName, value));
        if (messageIds?.size) {
            return (message) => messageIds.has(Number(message.id));
        }
        return (message) => this._getMessageSearchText(message).includes(value);
    },

    get currentSearchKeyword() {
        return this.searchMessageInput?.state?.searchTerm || "";
    },

    get searchSuggestionGroups() {
        const term = this.currentSearchKeyword.trim().toLowerCase();
        if (!term) {
            return [];
        }
        const regex = new RegExp(`(^|[\\s\\W_])${escapeRegExp(term)}([\\s\\W_]|$)`, "i");

        const fieldGroups = Object.entries(groupBy(this.suggestions, "fieldName"))
            .map(([fieldName, items]) =>
                this._buildFieldSuggestionGroup(fieldName, items, term, regex)
            )
            .filter(Boolean)
            .sort((a, b) => Number(a._fieldMatched) - Number(b._fieldMatched));

        return [
            { key: MESSAGE_GROUP_KEY, label: "Message", items: [], expandable: false },
            ...fieldGroups,
        ];
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
            matches = items.filter((item) => {
                const text = item.displayName.toLowerCase();
                return regex.test(text) || text === term;
            });
            if (!matches.length) {
                return null;
            }
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
        Object.assign(this.advancedFilterState.filters, this.createEmptyFilters());
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
        if (group.key.startsWith(FIELD_GROUP_PREFIX)) {
            if (item) {
                this.selectFieldSuggestion(group.fieldName, item, group.label);
            }
        } else if (group.key === MESSAGE_GROUP_KEY) {
            this.selectMessageSuggestion();
        }
    },

    selectFieldSuggestion(fieldName, item, fieldLabel) {
        const filters = this.advancedFilterState.filters;
        Object.assign(filters, {
            keyword: item.displayName,
            activeKeyword: item.displayName,
            activeKeywordMode: KEYWORD_MODE.FIELD,
            fieldName,
            fieldLabel,
            fieldValue: item.rawValue,
            fieldValueLabel: item.displayName,
        });
        this._resetFilters(filters, "message", "activity");
        this._closeSuggestionsAndNotify();
    },

    selectMessageSuggestion() {
        const filters = this.advancedFilterState.filters;
        const keyword = filters.keyword.trim();
        if (!keyword) {
            return;
        }
        filters.activeKeyword = keyword;
        filters.activeKeywordMode = KEYWORD_MODE.MESSAGE;
        this.clearFieldSelection(filters);
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

    getMessageDate(message) {
        const date = message?.date;
        if (!date) {
            return null;
        }
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
        if (!messages.length && !activities.length) {
            return;
        }

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
        if (!ids.length) {
            return new Map();
        }
        const audits = await this.orm.searchRead(model, [["id", "in", ids]], AUDIT_FIELDS, {
            limit: ids.length,
        });
        return new Map(audits.map((audit) => [Number(audit.id), audit]));
    },

    _auditInfo(audit = {}) {
        return {
            createDate: audit.create_date || "",
            createdBy: this._relationName(audit.create_uid),
            updatedDate: audit.write_date || "",
            updatedBy: this._relationName(audit.write_uid),
        };
    },

    _messageExportRecord(message, audit) {
        const typeOption = this.messageTypeOptions.find((t) => t.value === message.message_type);
        return {
            id: message.id || "",
            ...this._auditInfo(audit),
            date: this.getMessageDate(message) || "",
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
            date: activity.date_deadline || "",
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