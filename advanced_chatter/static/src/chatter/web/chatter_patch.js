import { Chatter } from "@mail/chatter/web_portal/chatter";
import "@mail/chatter/web/chatter_patch";
import { prettifyMessageText } from "@mail/utils/common/format";
import { useSequential } from "@mail/utils/common/hooks";
import { status, useEffect, useState } from "@odoo/owl";
import { serializeDateTime } from "@web/core/l10n/dates";
import { download } from "@web/core/network/download";
import { user } from "@web/core/user";
import { KeepLast } from "@web/core/utils/concurrency";
import { patch } from "@web/core/utils/patch";

Chatter.props.push("advancesearch?", "advancefilter?");
Object.assign(Chatter.defaultProps, { advancesearch: true, advancefilter: true });

/** @type {import("@mail/chatter/web_portal/chatter").Chatter} */
const chatterPatch = {
    setup() {
        super.setup(...arguments);
        this.advancedOptionsKeepLast = new KeepLast();
        this.advancedSuggestionsKeepLast = new KeepLast();
        this.advancedSearchSequential = useSequential();
        this.advancedSearchState = useState({
            hasAccess: false,
            options: {},
            values: {},
            dateFrom: null,
            dateTo: null,
            selection: null,
            keyword: null,
            typedTerm: "",
            suggestions: [],
            showSuggestions: false,
        });
        this.advancedMessageFetchKeyUsed = this.advancedMessageFetchKey;
        this.messageSearch.search = (before = false) => this.searchAdvancedMessages(before);

        user.hasGroup("advanced_chatter.group_advanced_chatter_user").then((hasAccess) => {
            if (status(this) !== "destroyed") {
                this.advancedSearchState.hasAccess = hasAccess;
            }
        });

        useEffect(
            (fetchKey) => {
                if (fetchKey === this.advancedMessageFetchKeyUsed) {
                    return;
                }
                this.advancedMessageFetchKeyUsed = fetchKey;
                if (this.state.isSearchOpen) {
                    this.messageSearch.search();
                }
            },
            () => [this.advancedMessageFetchKey]
        );
        useEffect(
            (hasAccess, isSearchOpen) => {
                if (hasAccess && isSearchOpen) {
                    this.loadAdvancedFilterOptions();
                }
            },
            () => [
                this.advancedSearchState.hasAccess,
                this.state.isSearchOpen,
                this.state.thread?.localId,
                this.messageSearch.is_notification,
                this.state.thread?.messages.length,
                super.activities.length,
            ]
        );
    },

    get childSubEnv() {
        return Object.assign(super.childSubEnv, { advancedChatterSearch: this });
    },

    get hasAdvancedChatterAccess() {
        return this.advancedSearchState.hasAccess;
    },

    get showAdvancedSearch() {
        return this.hasAdvancedChatterAccess && this.props.advancesearch;
    },

    get showAdvancedFilters() {
        return this.hasAdvancedChatterAccess && this.props.advancefilter;
    },

    /**
     * @param {number|false} [before]
     */
    async searchAdvancedMessages(before = false) {
        const messageSearch = this.messageSearch;
        const advanced = this.advancedMessageFetchParams;
        this.advancedMessageFetchKeyUsed = JSON.stringify(advanced);
        if (!advanced && !messageSearch.searchTerm && messageSearch.is_notification === undefined) {
            messageSearch.clear();
            return;
        }
        messageSearch.searching = true;
        const data = await this.advancedSearchSequential(() =>
            this.store.searchMessagesInThread(
                advanced?.ignoreSearchTerm ? "" : messageSearch.searchTerm,
                messageSearch.thread,
                before,
                messageSearch.is_notification,
                advanced?.fetchParams
            )
        );
        if (!data) {
            return;
        }
        const { count, loadMore, messages } = data;
        messageSearch.searched = true;
        messageSearch.searching = false;
        messageSearch.count = count;
        messageSearch.loadMore = loadMore;
        if (before) {
            messageSearch.messages.push(...messages);
        } else {
            messageSearch.messages = messages;
        }
    },

    async loadAdvancedFilterOptions() {
        const thread = this.state.thread;
        if (!thread?.id) {
            return;
        }
        let options;
        try {
            options = await this.advancedOptionsKeepLast.add(
                this.orm.call(thread.model, "get_advanced_chatter_filter_options", [[thread.id]], {
                    is_notification: this.messageSearch.is_notification ?? null,
                })
            );
        } catch {
            options = {};
        }
        if (status(this) === "destroyed") {
            return;
        }
        this.advancedSearchState.options = options;
        const values = {};
        for (const kind of ["message", "activity"]) {
            for (const group of options[kind]?.groups ?? []) {
                const key = this.filterKey(kind, group);
                const value = this.advancedSearchState.values[key];
                if (group.options.some((option) => option.value === value)) {
                    values[key] = value;
                }
            }
        }
        this.advancedSearchState.values = values;
    },

    get messageFilterGroups() {
        return this.advancedSearchState.options.message?.groups ?? [];
    },

    get activityFilterGroups() {
        return this.advancedSearchState.options.activity?.groups ?? [];
    },

    get messageDateField() {
        return this.advancedSearchState.options.message?.date_field;
    },

    get activityDateField() {
        return this.advancedSearchState.options.activity?.date_field;
    },

    get isSearchFilterActive() {
        return this.messageSearch.is_notification !== undefined;
    },

    get showActivityFilters() {
        return this.props.has_activities && !this.isSearchFilterActive && super.activities.length > 0;
    },

    isFilterGroupVisible(kind, group) {
        return (
            !this.isSearchFilterActive ||
            group.options.length > 1 ||
            this.getFilterValue(kind, group) !== ""
        );
    },

    filterKey(kind, group) {
        return `${kind}:${group.field}`;
    },

    getFilterValue(kind, group) {
        return this.advancedSearchState.values[this.filterKey(kind, group)] ?? "";
    },

    setFilterValue(kind, group, rawValue) {
        const option = group.options.find((option) => String(option.value) === rawValue);
        const values = { ...this.advancedSearchState.values };
        if (option) {
            values[this.filterKey(kind, group)] = option.value;
        } else {
            delete values[this.filterKey(kind, group)];
        }
        this.advancedSearchState.values = values;
        if (kind === "message") {
            this._clearAdvancedActivityFilters();
        } else {
            this._clearAdvancedMessageFilters();
        }
    },

    setDateFilter(key, value) {
        this.advancedSearchState[key] = value || null;
    },

    _activeFilters(kind) {
        const groups = kind === "message" ? this.messageFilterGroups : this.activityFilterGroups;
        return groups
            .map((group) => [group, this.advancedSearchState.values[this.filterKey(kind, group)]])
            .filter(([, value]) => value !== undefined);
    },

    _clearAdvancedMessageFilters() {
        const values = { ...this.advancedSearchState.values };
        for (const group of this.messageFilterGroups) {
            delete values[this.filterKey("message", group)];
        }
        this.advancedSearchState.values = values;
        this.advancedSearchState.keyword = null;
        if (this.advancedSearchState.selection?.kind !== "activity") {
            this.advancedSearchState.selection = null;
        }
    },

    _clearAdvancedActivityFilters() {
        const values = { ...this.advancedSearchState.values };
        for (const group of this.activityFilterGroups) {
            delete values[this.filterKey("activity", group)];
        }
        this.advancedSearchState.values = values;
        if (this.advancedSearchState.selection?.kind === "activity") {
            this.advancedSearchState.selection = null;
        }
    },

    onSearchFilterChanged() {
        this._clearAdvancedActivityFilters();
    },

    clearAdvancedFilters() {
        Object.assign(this.advancedSearchState, {
            values: {},
            dateFrom: null,
            dateTo: null,
            selection: null,
            keyword: null,
            showSuggestions: false,
        });
    },

    get isAdvancedActivityMode() {
        return (
            this.hasAdvancedChatterAccess &&
            (this._activeFilters("activity").length > 0 ||
                this.advancedSearchState.selection?.kind === "activity")
        );
    },

    get isAdvancedMessageMode() {
        return (
            this.hasAdvancedChatterAccess &&
            (this._activeFilters("message").length > 0 ||
                this.advancedSearchState.selection?.kind === "message" ||
                Boolean(this.advancedSearchState.keyword))
        );
    },

    get isAdvancedFilterActive() {
        const { dateFrom, dateTo } = this.advancedSearchState;
        return this.isAdvancedActivityMode || this.isAdvancedMessageMode || Boolean(dateFrom || dateTo);
    },

    get activeAdvancedFilterCount() {
        const { dateFrom, dateTo, selection, keyword } = this.advancedSearchState;
        return (
            this._activeFilters("message").length +
            this._activeFilters("activity").length +
            Number(Boolean(dateFrom || dateTo)) +
            Number(Boolean(selection || keyword))
        );
    },

    _dateDomain(field) {
        const { dateFrom, dateTo } = this.advancedSearchState;
        const domain = [];
        if (field && dateFrom) {
            domain.push([field.name, ">=", serializeDateTime(dateFrom.startOf("day"))]);
        }
        if (field && dateTo) {
            domain.push([field.name, "<=", serializeDateTime(dateTo.endOf("day"))]);
        }
        return domain;
    },

    get advancedMessageFetchParams() {
        if (!this.hasAdvancedChatterAccess || this.isAdvancedActivityMode) {
            return null;
        }
        const { selection } = this.advancedSearchState;
        const domain = [
            ...this._activeFilters("message").map(([group, value]) => [group.field, "=", value]),
            ...this._dateDomain(this.messageDateField),
            ...(selection?.kind === "message" ? selection.domain : []),
        ];
        if (!domain.length) {
            return null;
        }
        return {
            fetchParams: { advanced_domain: domain },
            ignoreSearchTerm: selection?.kind === "message",
        };
    },

    get advancedMessageFetchKey() {
        return JSON.stringify(this.advancedMessageFetchParams);
    },

    _isActivityInDateRange(activity) {
        const field = this.activityDateField;
        const { dateFrom, dateTo } = this.advancedSearchState;
        if (!field || (!dateFrom && !dateTo)) {
            return true;
        }
        const value = activity[field.name];
        if (!value) {
            return false;
        }
        return (
            (!dateFrom || value >= dateFrom.startOf("day")) &&
            (!dateTo || value <= dateTo.endOf("day"))
        );
    },

    _activityMatchesFilters(activity) {
        const { selection } = this.advancedSearchState;
        if (selection?.kind === "activity" && !selection.activity_ids.includes(activity.id)) {
            return false;
        }
        return (
            this._isActivityInDateRange(activity) &&
            this._activeFilters("activity").every(([group, value]) => {
                const recordValue = activity[group.field];
                return (recordValue?.id ?? recordValue) === value;
            })
        );
    },

    get activities() {
        const activities = super.activities;
        if (!this.hasAdvancedChatterAccess) {
            return activities;
        }
        if (this.isSearchFilterActive || this.isAdvancedMessageMode) {
            return [];
        }
        return activities.filter((activity) => this._activityMatchesFilters(activity));
    },

    get isAdvancedActivityListVisible() {
        return (
            this.activities.length > 0 &&
            (this.isAdvancedFilterActive ||
                (!this.messageSearch.searching && !this.messageSearch.searched))
        );
    },

    get isAdvancedEmptyResult() {
        return this.isAdvancedActivityMode && !this.activities.length;
    },

    async onKeywordTyped(term) {
        Object.assign(this.advancedSearchState, {
            selection: null,
            keyword: null,
            typedTerm: term,
            suggestions: [],
            showSuggestions: Boolean(term.trim()) && this.showAdvancedSearch,
        });
        const thread = this.state.thread;
        if (!this.advancedSearchState.showSuggestions || !thread?.id) {
            return;
        }
        let suggestions;
        try {
            suggestions = await this.advancedSuggestionsKeepLast.add(
                this.orm.call(thread.model, "get_advanced_chatter_suggestions", [[thread.id], term], {
                    is_notification: this.messageSearch.is_notification ?? null,
                })
            );
        } catch {
            suggestions = [];
        }
        if (status(this) !== "destroyed" && this.advancedSearchState.typedTerm === term) {
            this.advancedSearchState.suggestions = this.props.has_activities
                ? suggestions
                : suggestions.filter((group) => group.kind !== "activity");
        }
    },

    selectKeywordSuggestion(term) {
        term = term.trim();
        if (!term) {
            return;
        }
        this._clearAdvancedActivityFilters();
        this.advancedSearchState.selection = null;
        this.advancedSearchState.keyword = term;
        this.advancedSearchState.showSuggestions = false;
    },

    selectSuggestion(group, item) {
        this.advancedSearchState.keyword = null;
        if (group.kind === "activity") {
            this._clearAdvancedMessageFilters();
        } else {
            this._clearAdvancedActivityFilters();
        }
        this.advancedSearchState.selection = { kind: group.kind, label: item.label, ...item };
        this.advancedSearchState.showSuggestions = false;
    },

    resetAdvancedSearch() {
        this.clearAdvancedFilters();
        this.advancedSearchState.typedTerm = "";
        this.advancedSearchState.suggestions = [];
    },

    async exportAdvancedResults() {
        const thread = this.state.thread;
        if (!thread?.id) {
            return;
        }
        const advanced = this.advancedMessageFetchParams;
        const searchTerm = advanced?.ignoreSearchTerm ? "" : this.messageSearch.searchTerm ?? "";
        const messages = this.isAdvancedActivityMode
            ? null
            : {
                  search_term: String(await prettifyMessageText(searchTerm)),
                  is_notification: this.messageSearch.is_notification ?? null,
                  advanced_domain: advanced?.fetchParams.advanced_domain ?? null,
              };
        const activityIds = this.isAdvancedActivityListVisible
            ? this.activities.map((activity) => activity.id)
            : null;
        await download({
            url: "/advanced_chatter/export/csv",
            data: {
                data: JSON.stringify({
                    thread_model: thread.model,
                    thread_id: thread.id,
                    messages,
                    activity_ids: activityIds,
                    context: user.context,
                }),
            },
        });
    },
};

patch(Chatter.prototype, chatterPatch);
