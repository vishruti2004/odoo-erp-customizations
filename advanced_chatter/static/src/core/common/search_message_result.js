/** @odoo-module **/

import { SearchMessageResult } from "@mail/core/common/search_message_result";
import { onWillDestroy } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(SearchMessageResult.prototype, {
    setup() {
        super.setup(...arguments);
        const chatter = this.env.advancedChatterSearch;
        if (chatter) {
            onWillDestroy(chatter.onFiltersChanged(() => this.render()));
        }
    },

    get filteredMessages() {
        const messages = this.props.messageSearch.messages;
        return this.env.advancedChatterSearch?._applyStructuredFilters(messages) ?? messages;
    },

    get MESSAGE_FOUND() {
        const total = this.props.messageSearch.messages.length;
        const shown = this.filteredMessages.length;
        if (shown === total) {
            return super.MESSAGE_FOUND;
        }
        return shown ? _t("%s messages found", shown) : false;
    },
});
