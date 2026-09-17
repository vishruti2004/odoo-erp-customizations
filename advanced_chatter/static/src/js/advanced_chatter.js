/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Thread } from "@mail/core/common/thread";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched, onWillStart, useState } from "@odoo/owl";

const PRODUCT_WITH_CODE_PATTERN =
    /\[([^\[\]<>]{1,30})\]\s*([^\[\]<\n]{2,80})/g;

const PRODUCT_WITHOUT_CODE_PATTERN =
    /Extra line with\s+([^\[\]<\n]{2,80})/gi;

patch(Thread.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");

        this.messageTypeOptions = [
            { value: "comment", label: "Comment" },
            { value: "email", label: "Incoming Email" },
            { value: "email_outgoing", label: "Outgoing Email" },
            { value: "notification", label: "System Notification" },
            { value: "auto_comment", label: "Automated Targeted Notification" },
        ];

        this.searchSuggestionDefinitions = [
            { key: "message", label: "Message", icon: "fa fa-search", expandable: false },
            { key: "product", label: "Product", icon: "fa fa-cube", expandable: true },
            { key: "author", label: "Author", icon: "fa fa-user", expandable: true },
            { key: "messageType", label: "Message Type", icon: "fa fa-envelope-o", expandable: true },
            { key: "subtype", label: "Message Subtype", icon: "fa fa-tag", expandable: true },
        ];

        this.advancedFilterState = useState({
            showAdvancedFilters: false,
            showSuggestions: false,
            expandedSuggestionGroup: null,
            applied: false,
            searching: false,

            filters: {
                keyword: "",
                dateFrom: "",
                dateTo: "",
                userId: "",
                authorKeyword: "",
                messageType: "",
                subtypeId: "",
                productId: "",
                productKeyword: "",
                includeActivities: false,
                activityTypeId: "",
                activityUserId: "",
                activityState: "",
            },

            subtypes: [],
            activityTypes: [],
            activities: [],
        });

        onWillStart(async () => {
            this.advancedFilterState.subtypes = await this.orm.searchRead(
                "mail.message.subtype",
                [],
                ["id", "name"],
                { limit: 200, order: "name asc" }
            );

            this.advancedFilterState.activityTypes = await this.orm.searchRead(
                "mail.activity.type",
                [],
                ["id", "name"],
                { limit: 200, order: "name asc" }
            );

            await this.loadConversationActivities();
        });

        onMounted(() => this.placeAdvancedSearchAboveActivities());
        onPatched(() => this.placeAdvancedSearchAboveActivities());
    },

    /**
     * Put the search/filter block above the native ActivityList
     * without moving Owl-managed DOM nodes.
     */
    placeAdvancedSearchAboveActivities() {
        if (!this.el) {
            return;
        }

        this.el.style.display = "contents";

        const search = this.el.querySelector(".o-advanced-chatter-main-search");
        const filters = this.el.querySelector(".o-advanced-chatter-filter-panel");

        if (search) {
            search.style.order = "-20";
            search.style.position = "relative";
            search.style.zIndex = "10";
        }

        if (filters) {
            filters.style.order = "-19";
            filters.style.position = "relative";
            filters.style.zIndex = "9";
        }
    },

    // ------------------------------------------------------------------
    // Messages
    // ------------------------------------------------------------------

    get threadMessages() {
        return this.orderedMessages || this.messages || [];
    },

    // ------------------------------------------------------------------
    // Conversation message data
    // ------------------------------------------------------------------

    get conversationAuthors() {
        const seen = new Set();
        const authors = [];

        for (const message of this.threadMessages) {
            const author = message.author;

            if (!author || !author.id || seen.has(author.id)) {
                continue;
            }

            seen.add(author.id);

            authors.push({
                id: author.id,
                name: author.name || "",
            });
        }

        authors.sort((a, b) => a.name.localeCompare(b.name));

        return authors;
    },

    get conversationMessageTypes() {
        const seen = new Set();

        for (const message of this.threadMessages) {
            if (message.message_type) {
                seen.add(message.message_type);
            }
        }

        return this.messageTypeOptions.filter((type) => seen.has(type.value));
    },

    get conversationSubtypes() {
        const seenIds = new Set();

        for (const message of this.threadMessages) {
            const subtypeId = message.subtype_id?.id ?? message.subtype_id;

            if (subtypeId) {
                seenIds.add(Number(subtypeId));
            }
        }

        return this.advancedFilterState.subtypes.filter(
            (subtype) => seenIds.has(Number(subtype.id))
        );
    },

    // ------------------------------------------------------------------
    // Conversation activities
    // ------------------------------------------------------------------

    get conversationActivities() {
        return this.advancedFilterState.activities || [];
    },

    getMany2OneValue(value) {
        if (Array.isArray(value)) {
            return {
                id: value[0] || null,
                name: value[1] || "",
            };
        }

        if (value && typeof value === "object") {
            return {
                id: value.id || value.res_id || null,
                name: value.display_name || value.name || "",
            };
        }

        return {
            id: value || null,
            name: "",
        };
    },

    get conversationActivityTypes() {
        const seen = new Set();
        const result = [];

        for (const activity of this.conversationActivities) {
            const value = this.getMany2OneValue(activity.activity_type_id);

            if (!value.id || seen.has(Number(value.id))) {
                continue;
            }

            seen.add(Number(value.id));

            result.push({
                id: Number(value.id),
                name: value.name || "",
            });
        }

        result.sort((a, b) => a.name.localeCompare(b.name));

        return result;
    },

    get conversationActivityUsers() {
        const seen = new Set();
        const result = [];

        for (const activity of this.conversationActivities) {
            const value = this.getMany2OneValue(activity.user_id);

            if (!value.id || seen.has(Number(value.id))) {
                continue;
            }

            seen.add(Number(value.id));

            result.push({
                id: Number(value.id),
                name: value.name || "",
            });
        }

        result.sort((a, b) => a.name.localeCompare(b.name));

        return result;
    },

    get conversationActivityStates() {
        const labels = {
            overdue: "Overdue",
            today: "Today",
            planned: "Planned",
        };

        const seen = new Set();
        const result = [];

        for (const activity of this.conversationActivities) {
            if (!activity.state || seen.has(activity.state)) {
                continue;
            }

            seen.add(activity.state);

            result.push({
                value: activity.state,
                label: labels[activity.state] || activity.state,
            });
        }

        result.sort((a, b) => a.label.localeCompare(b.label));

        return result;
    },

    async loadConversationActivities() {
        const thread = this.props.thread;

        if (!thread?.model || !thread?.id) {
            this.advancedFilterState.activities = [];
            return;
        }

        this.advancedFilterState.activities = await this.orm.searchRead(
            "mail.activity",
            [
                ["res_model", "=", thread.model],
                ["res_id", "=", Number(thread.id)],
            ],
            [
                "id",
                "summary",
                "note",
                "activity_type_id",
                "date_deadline",
                "user_id",
                "res_model",
                "res_id",
                "res_name",
                "state",
            ],
            { limit: 200, order: "date_deadline asc, id asc" }
        );
    },

    // ------------------------------------------------------------------
    // Products
    // ------------------------------------------------------------------

    get conversationProducts() {
        const seen = new Set();
        const products = [];

        const addProduct = (defaultCode, rawName) => {
            const name = rawName.trim().replace(/\s+/g, " ");

            if (!name) {
                return;
            }

            const key = `${defaultCode.toLowerCase()}|${name.toLowerCase()}`;

            if (seen.has(key)) {
                return;
            }

            seen.add(key);

            products.push({
                id: `chatter-product-${products.length + 1}`,
                name,
                default_code: defaultCode,
                searchText: `${defaultCode} ${name}`.toLowerCase(),
            });
        };

        for (const message of this.threadMessages) {
            const text =
                `${this.getMessageText(message.subject)} ` +
                `${this.getMessageText(message.body)}`;

            let match;

            PRODUCT_WITH_CODE_PATTERN.lastIndex = 0;
            while ((match = PRODUCT_WITH_CODE_PATTERN.exec(text)) !== null) {
                addProduct(match[1].trim(), match[2]);
            }

            PRODUCT_WITHOUT_CODE_PATTERN.lastIndex = 0;
            while ((match = PRODUCT_WITHOUT_CODE_PATTERN.exec(text)) !== null) {
                addProduct("", match[1]);
            }
        }

        return products;
    },

    // ------------------------------------------------------------------
    // Search suggestions
    // ------------------------------------------------------------------

    get searchSuggestionGroups() {
        const keyword = this.advancedFilterState.filters.keyword.trim();

        if (!keyword) {
            return [];
        }

        const groups = [];

        for (const definition of this.searchSuggestionDefinitions) {
            if (definition.key === "message") {
                groups.push({
                    ...definition,
                    items: [],
                    expandable: false,
                });

                continue;
            }

            const items = this.getSuggestionItems(definition.key);

            if (!items.length) {
                continue;
            }

            groups.push({
                ...definition,
                items,
                expandable: items.length > 1,
            });
        }

        return groups;
    },

    getSuggestionItems(key) {
        switch (key) {
            case "product":
                return this.matchingProductSuggestions;

            case "author":
                return this.matchingAuthorSuggestions;

            case "messageType":
                return this.matchingMessageTypeSuggestions;

            case "subtype":
                return this.matchingSubtypeSuggestions;

            default:
                return [];
        }
    },

    get matchingProductSuggestions() {
        const term = this.advancedFilterState.filters.keyword
            .trim()
            .toLowerCase();

        if (!term) {
            return [];
        }

        return this.conversationProducts
            .filter(
                (product) =>
                    product.name.toLowerCase().includes(term) ||
                    product.default_code.toLowerCase().includes(term)
            )
            .slice(0, 5);
    },

    get matchingAuthorSuggestions() {
        const term = this.advancedFilterState.filters.keyword
            .trim()
            .toLowerCase();

        if (!term) {
            return [];
        }

        return this.conversationAuthors
            .filter((user) => user.name.toLowerCase().includes(term))
            .slice(0, 5);
    },

    get matchingMessageTypeSuggestions() {
        const term = this.advancedFilterState.filters.keyword
            .trim()
            .toLowerCase();

        if (!term) {
            return [];
        }

        return this.conversationMessageTypes
            .filter((type) => type.label.toLowerCase().includes(term))
            .slice(0, 5);
    },

    get matchingSubtypeSuggestions() {
        const term = this.advancedFilterState.filters.keyword
            .trim()
            .toLowerCase();

        if (!term) {
            return [];
        }

        return this.conversationSubtypes
            .filter((subtype) => subtype.name.toLowerCase().includes(term))
            .slice(0, 5);
    },

    // ------------------------------------------------------------------
    // Search UI
    // ------------------------------------------------------------------

    toggleAdvancedFilters() {
        this.advancedFilterState.showAdvancedFilters =
            !this.advancedFilterState.showAdvancedFilters;

        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
    },

    onKeywordInput(ev) {
        this.advancedFilterState.filters.keyword = ev.target.value;
        this.advancedFilterState.showSuggestions = !!ev.target.value.trim();
        this.advancedFilterState.expandedSuggestionGroup = null;
    },

    onKeywordFocus() {
        if (this.advancedFilterState.filters.keyword.trim()) {
            this.advancedFilterState.showSuggestions = true;
        }
    },

    clearKeywordSearch() {
        this.advancedFilterState.filters.keyword = "";
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.applyAdvancedFilters();
    },

    onKeywordBlur() {
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
    },

    onKeywordKeydown(ev) {
        if (ev.key === "Enter") {
            this.advancedFilterState.showSuggestions = false;
            this.advancedFilterState.expandedSuggestionGroup = null;
            this.applyAdvancedFilters();
        }

        if (ev.key === "Escape") {
            this.advancedFilterState.showSuggestions = false;
            this.advancedFilterState.expandedSuggestionGroup = null;
        }
    },

    toggleSuggestionGroup(groupKey) {
        this.advancedFilterState.expandedSuggestionGroup =
            this.advancedFilterState.expandedSuggestionGroup === groupKey
                ? null
                : groupKey;
    },

    selectSearchSuggestion(group, item = null) {
        switch (group.key) {
            case "message":
                this.selectMessageSuggestion();
                break;

            case "product":
                if (item) {
                    this.selectProductSuggestion(item);
                }
                break;

            case "author":
                if (item) {
                    this.selectAuthorSuggestion(item);
                } else {
                    this.selectAuthorGroupSuggestion();
                }
                break;

            case "messageType":
                if (item) {
                    this.selectMessageTypeSuggestion(item);
                }
                break;

            case "subtype":
                if (item) {
                    this.selectSubtypeSuggestion(item);
                }
                break;
        }
    },

    selectMessageSuggestion() {
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.applyAdvancedFilters();
    },

    selectAuthorSuggestion(user) {
        this.advancedFilterState.filters.userId = user.id;
        this.resetKeywordAndApply();
    },

    selectAuthorGroupSuggestion() {
        this.advancedFilterState.filters.authorKeyword =
            this.advancedFilterState.filters.keyword.trim();
        this.resetKeywordAndApply();
    },

    selectMessageTypeSuggestion(type) {
        this.advancedFilterState.filters.messageType = type.value;
        this.resetKeywordAndApply();
    },

    selectSubtypeSuggestion(subtype) {
        this.advancedFilterState.filters.subtypeId = subtype.id;
        this.resetKeywordAndApply();
    },

    selectProductSuggestion(product) {
        this.advancedFilterState.filters.productId = product.id;
        this.advancedFilterState.filters.productKeyword =
            product.searchText || product.name || "";
        this.resetKeywordAndApply();
    },

    resetKeywordAndApply() {
        this.advancedFilterState.filters.keyword = "";
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.applyAdvancedFilters();
    },

    // ------------------------------------------------------------------
    // Advanced Filters
    // ------------------------------------------------------------------

    clearAdvancedFilters() {
        this.advancedFilterState.filters = {
            keyword: "",
            dateFrom: "",
            dateTo: "",
            userId: "",
            authorKeyword: "",
            messageType: "",
            subtypeId: "",
            productId: "",
            productKeyword: "",
            includeActivities: false,
            activityTypeId: "",
            activityUserId: "",
            activityState: "",
        };

        this.advancedFilterState.applied = false;
        this.advancedFilterState.searching = false;
        this.advancedFilterState.showSuggestions = false;
        this.advancedFilterState.expandedSuggestionGroup = null;
        this.advancedFilterState.activities = [];
    },

    async applyAdvancedFilters() {
        this.advancedFilterState.applied = true;
        this.advancedFilterState.searching = true;

        try {
            if (this.advancedFilterState.filters.includeActivities) {
                await this.searchActivities();
            } else {
                this.advancedFilterState.activities = [];
            }
        } finally {
            this.advancedFilterState.searching = false;
        }
    },

    // ------------------------------------------------------------------
    // Message Filtering
    // ------------------------------------------------------------------

    get filteredMessages() {
        const messages = this.threadMessages;

        if (!this.advancedFilterState.applied) {
            return messages;
        }

        const filters = this.advancedFilterState.filters;

        return messages.filter((message) => {
            const body = this.getMessageText(message.body);
            const subject = this.getMessageText(message.subject);
            const messageText = `${subject} ${body}`.toLowerCase();

            if (filters.keyword) {
                if (!messageText.includes(filters.keyword.trim().toLowerCase())) {
                    return false;
                }
            }

            if (filters.productId) {
                const productSearchText = filters.productKeyword
                    .trim()
                    .toLowerCase();

                if (!productSearchText || !messageText.includes(productSearchText)) {
                    return false;
                }
            }

            if (filters.dateFrom) {
                const messageDate = this.getMessageDate(message);

                if (!messageDate || messageDate < filters.dateFrom) {
                    return false;
                }
            }

            if (filters.dateTo) {
                const messageDate = this.getMessageDate(message);

                if (!messageDate || messageDate > filters.dateTo) {
                    return false;
                }
            }

            if (filters.userId) {
                const authorId = message.author?.id;

                if (!authorId || Number(authorId) !== Number(filters.userId)) {
                    return false;
                }
            }

            if (filters.authorKeyword) {
                const authorName = (message.author?.name || "").toLowerCase();

                if (!authorName.includes(filters.authorKeyword.toLowerCase())) {
                    return false;
                }
            }

            if (filters.messageType && message.message_type !== filters.messageType) {
                return false;
            }

            if (filters.subtypeId) {
                const subtypeId = message.subtype_id?.id || message.subtype_id;

                if (Number(subtypeId) !== Number(filters.subtypeId)) {
                    return false;
                }
            }

            return true;
        });
    },

    // ------------------------------------------------------------------
    // Activity Filtering
    // ------------------------------------------------------------------

    async searchActivities() {
        const filters = this.advancedFilterState.filters;
        const thread = this.props.thread;

        const domain = [];

        if (thread?.model) {
            domain.push(["res_model", "=", thread.model]);
        }

        if (thread?.id) {
            domain.push(["res_id", "=", Number(thread.id)]);
        }

        if (filters.dateFrom) {
            domain.push(["date_deadline", ">=", filters.dateFrom]);
        }

        if (filters.dateTo) {
            domain.push(["date_deadline", "<=", filters.dateTo]);
        }

        if (filters.activityUserId) {
            domain.push(["user_id", "=", Number(filters.activityUserId)]);
        }

        if (filters.activityTypeId) {
            domain.push(["activity_type_id", "=", Number(filters.activityTypeId)]);
        }

        if (filters.activityState) {
            domain.push(["state", "=", filters.activityState]);
        }

        this.advancedFilterState.activities = await this.orm.searchRead(
            "mail.activity",
            domain,
            [
                "id",
                "summary",
                "note",
                "activity_type_id",
                "date_deadline",
                "user_id",
                "res_model",
                "res_id",
                "res_name",
                "state",
            ],
            { limit: 200, order: "date_deadline asc, id asc" }
        );
    },

    get filteredActivities() {
        if (!this.advancedFilterState.filters.includeActivities) {
            return [];
        }

        return this.advancedFilterState.activities || [];
    },

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    getMessageDate(message) {
        if (!message?.date) {
            return null;
        }

        try {
            if (typeof message.date.toISODate === "function") {
                return message.date.toISODate();
            }

            if (typeof message.date === "string") {
                return message.date.substring(0, 10);
            }
        } catch {
            return null;
        }

        return null;
    },

    getMessageText(value) {
        if (!value) {
            return "";
        }

        if (typeof value === "string") {
            const container = document.createElement("div");
            container.innerHTML = value;

            return (container.textContent || container.innerText || "").replace(
                /<[^>]*>/g,
                " "
            );
        }

        return String(value).replace(/<[^>]*>/g, " ");
    },

    // ------------------------------------------------------------------
    // Export
    // ------------------------------------------------------------------

    exportAdvancedResults() {
        const messages = this.filteredMessages || [];
        const activities = this.filteredActivities || [];

        if (!messages.length && !activities.length) {
            return;
        }

        const rows = [
            [
                "Result Type",
                "ID",
                "Date",
                "User / Author",
                "Message Type",
                "Subject / Summary",
                "Message / Note",
            ],
        ];

        for (const message of messages) {
            rows.push([
                "Message",
                message.id || "",
                this.getMessageDate(message) || "",
                message.author?.name || "",
                message.message_type || "",
                this.getMessageText(message.subject),
                this.getMessageText(message.body),
            ]);
        }

        for (const activity of activities) {
            rows.push([
                "Activity",
                activity.id || "",
                activity.date_deadline || "",
                activity.user_id?.[1] || "",
                activity.activity_type_id?.[1] || "",
                activity.summary || "",
                this.getMessageText(activity.note),
            ]);
        }

        const csv = rows
            .map((row) =>
                row
                    .map(
                        (value) =>
                            `"${String(value ?? "")
                                .replace(/"/g, '""')
                                .replace(/\r?\n/g, " ")}"`
                    )
                    .join(",")
            )
            .join("\n");

        const blob = new Blob(["\ufeff" + csv], {
            type: "text/csv;charset=utf-8;",
        });

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