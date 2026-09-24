/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SearchMessageInput } from "@mail/core/common/search_message_input";
import { useDropdownState } from "@web/core/dropdown/dropdown_hooks";
import { onWillDestroy, useState } from "@odoo/owl";

patch(SearchMessageInput.prototype, {
    setup() {
        super.setup(...arguments);

        this.advancedDropdownState = useState({
            expandedGroup: null,
        });

        this.filterDropdownState = useDropdownState();

        const chatter = this.env.advancedChatterSearch;

        if (!chatter) {
            return;
        }

        chatter.searchMessageInput = this;

        if (typeof chatter.onFiltersChanged === "function") {
            const unsubscribe = chatter.onFiltersChanged((shouldClose = true) => {
                this.render();

                if (shouldClose) {
                    this.filterDropdownState.close();
                }
            });

            onWillDestroy(unsubscribe);
        }

        onWillDestroy(() => {
            if (chatter.searchMessageInput === this) {
                chatter.searchMessageInput = null;
            }
        });
    },

    search() {
        // original search behavior.
        super.search(...arguments);
    },

    clear() {
        //original clear behavior.
        super.clear();

        const chatter = this.env.advancedChatterSearch;

        if (chatter?.clearAdvancedFilters) {
            chatter.clearAdvancedFilters();
        }
    },

    toggleAdvancedGroup(key) {
        this.advancedDropdownState.expandedGroup =
            this.advancedDropdownState.expandedGroup === key
                ? null
                : key;
    },

    onKeywordSync() {
        const chatter = this.env.advancedChatterSearch;

        if (!chatter) {
            return;
        }

        setTimeout(() => {
            const typed = this.state.searchTerm || "";
            const filters = chatter.advancedFilterState.filters;

            filters.keyword = typed;
            filters.activeKeyword = "";
            filters.activeKeywordMode = "";

            chatter.clearFieldSelection(filters);

            chatter.advancedFilterState.showSuggestions = !!typed.trim();
            this.advancedDropdownState.expandedGroup = null;

            if (typed.trim()) {
                chatter._ensureExtracted().then(() => {
                    chatter.notifyFiltersChanged(false);
                });
            }
        }, 0);
    },

    onKeywordFocusSync() {
        const chatter = this.env.advancedChatterSearch;

        if (chatter && this.state.searchTerm.trim()) {
            chatter.advancedFilterState.showSuggestions = true;
        }
    },

    onKeywordBlurSync() {
        const chatter = this.env.advancedChatterSearch;

        if (!chatter) {
            return;
        }

        setTimeout(() => {
            chatter.advancedFilterState.showSuggestions = false;
            this.advancedDropdownState.expandedGroup = null;
        }, 200);
    },

    selectSuggestionAndSync(group, item = null) {
        const chatter = this.env.advancedChatterSearch;

        if (!chatter) {
            return;
        }

        chatter.selectSearchSuggestion(group, item);
    },
});