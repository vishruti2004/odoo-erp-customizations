/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Thread } from "@mail/core/common/thread";
import { onWillDestroy } from "@odoo/owl";

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

        if (!chatter) {
            return this.orderedMessages || [];
        }
        const filtered = chatter.filteredMessages || [];
        return this.props.order === "asc"
            ? [...filtered]
            : [...filtered].reverse();
    },
});