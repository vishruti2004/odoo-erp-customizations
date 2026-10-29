import { SearchMessageInput } from "@mail/core/common/search_message_input";
import { onWillDestroy, useEffect, useState } from "@odoo/owl";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { patch } from "@web/core/utils/patch";

Object.assign(SearchMessageInput.components, { DateTimeInput });

patch(SearchMessageInput.prototype, {
    setup() {
        super.setup(...arguments);
        this.advancedDropdownState = useState({ expandedGroup: null });
        this.filterDropdownState = useDropdownState();
        const chatter = this.advancedChatter;
        if (!chatter) {
            return;
        }
        let typedTerm = this.state.searchTerm;
        useEffect(
            (term) => {
                if (term === typedTerm) {
                    return;
                }
                typedTerm = term;
                this.advancedDropdownState.expandedGroup = null;
                chatter.onKeywordTyped(term || "");
            },
            () => [this.state.searchTerm]
        );
        onWillDestroy(() => chatter.resetAdvancedSearch());
    },

    get advancedChatter() {
        return this.env.advancedChatterSearch;
    },

    onKeydownSearch(ev) {
        super.onKeydownSearch(ev);
        if (ev.key === "Enter" && this.advancedChatter) {
            this.advancedChatter.advancedSearchState.showSuggestions = false;
        }
    },

    onChangeSearchFilter(searchFilter) {
        super.onChangeSearchFilter(searchFilter);
        this.advancedChatter?.onSearchFilterChanged();
    },

    clear() {
        this.advancedChatter?.clearAdvancedFilters();
        super.clear();
    },

    onAdvancedFilterChange(kind, group, value) {
        this.advancedChatter.setFilterValue(kind, group, value);
        this.filterDropdownState.close();
    },

    onAdvancedDateApply(key, value) {
        const chatter = this.advancedChatter;
        chatter.setDateFilter(key, value);
        if (chatter.advancedSearchState.dateFrom && chatter.advancedSearchState.dateTo) {
            this.filterDropdownState.close();
        }
    },

    onAdvancedClearFilters() {
        this.advancedChatter.clearAdvancedFilters();
        this.filterDropdownState.close();
    },

    toggleAdvancedGroup(key) {
        this.advancedDropdownState.expandedGroup =
            this.advancedDropdownState.expandedGroup === key ? null : key;
    },

    selectAdvancedKeyword() {
        this.advancedChatter.selectKeywordSuggestion(this.state.searchTerm);
        this.advancedDropdownState.expandedGroup = null;
        this.search();
    },

    selectAdvancedSuggestion(group, item) {
        this.advancedChatter.selectSuggestion(group, item);
        this.advancedDropdownState.expandedGroup = null;
    },

    _isAdvancedSearchInput(ev) {
        return ev.target?.tagName === "INPUT" && ev.target.type === "text";
    },

    onAdvancedFocusIn(ev) {
        const chatter = this.advancedChatter;
        if (!chatter || !this._isAdvancedSearchInput(ev)) {
            return;
        }
        if (this.state.searchTerm.trim() && chatter.showAdvancedSearch) {
            chatter.advancedSearchState.showSuggestions = true;
        }
    },

    onAdvancedFocusOut(ev) {
        const chatter = this.advancedChatter;
        if (!chatter || !this._isAdvancedSearchInput(ev)) {
            return;
        }
        chatter.advancedSearchState.showSuggestions = false;
        this.advancedDropdownState.expandedGroup = null;
    },
});
