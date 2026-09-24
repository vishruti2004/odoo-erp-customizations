/** @odoo-module **/

import { SearchMessageInput } from "@mail/core/common/search_message_input";
import { onWillDestroy, useState } from "@odoo/owl";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { patch } from "@web/core/utils/patch";

const BLUR_CLOSE_DELAY = 200;

patch(SearchMessageInput.prototype, {
    get advancedChatter() {
        return this.env.advancedChatterSearch;
    },

    setup() {
        super.setup(...arguments);

        this.advancedDropdownState = useState({ expandedGroup: null });
        this.filterDropdownState = useDropdownState();

        const chatter = this.advancedChatter;
        if (!chatter) {
            return;
        }

        chatter.searchMessageInput = this;
        chatter.onSearchFilterChanged(this.props.messageSearch.is_notification);

        const unsubscribe = chatter.onFiltersChanged((shouldClose = true) => {
            this.render();
            if (shouldClose) {
                this.filterDropdownState.close();
            }
        });

        onWillDestroy(() => {
            unsubscribe();
            chatter.onSearchFilterChanged(undefined);
            if (chatter.searchMessageInput === this) {
                chatter.searchMessageInput = null;
            }
        });
    },

    onChangeSearchFilter(searchFilter) {
        const chatter = this.advancedChatter;
        const { messageSearch } = this.props;
        const isClientOnly =
            chatter &&
            !messageSearch.searched &&
            !messageSearch.searching &&
            !this.state.searchTerm.trim();
        if (isClientOnly) {
            messageSearch.is_notification = searchFilter.is_notification;
        } else {
            super.onChangeSearchFilter(searchFilter);
        }
        chatter?.onSearchFilterChanged(searchFilter.is_notification);
    },

    clear() {
        super.clear();
        this.advancedChatter?.clearAdvancedFilters();
    },

    toggleAdvancedGroup(key) {
        const state = this.advancedDropdownState;
        state.expandedGroup = state.expandedGroup === key ? null : key;
    },

    onKeywordSync() {
        const chatter = this.advancedChatter;
        if (!chatter) {
            return;
        }
        setTimeout(() => {
            const typed = this.state.searchTerm || "";
            chatter._resetFilters("keyword", "field");
            chatter.advancedFilterState.filters.keyword = typed;
            chatter.advancedFilterState.showSuggestions = Boolean(typed.trim());
            this.advancedDropdownState.expandedGroup = null;
            if (typed.trim()) {
                chatter._ensureExtracted().then(() => chatter.notifyFiltersChanged(false));
            }
        }, 0);
    },

    onKeywordFocusSync() {
        const chatter = this.advancedChatter;
        if (chatter && this.state.searchTerm.trim()) {
            chatter.advancedFilterState.showSuggestions = true;
        }
    },

    onKeywordBlurSync() {
        const chatter = this.advancedChatter;
        if (!chatter) {
            return;
        }
        setTimeout(() => {
            chatter.advancedFilterState.showSuggestions = false;
            this.advancedDropdownState.expandedGroup = null;
        }, BLUR_CLOSE_DELAY);
    },

    selectSuggestionAndSync(group, item = null) {
        this.advancedChatter?.selectSearchSuggestion(group, item);
    },
});
