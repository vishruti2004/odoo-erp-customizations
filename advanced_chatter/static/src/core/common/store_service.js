import { Store } from "@mail/core/common/store_service";
import { prettifyMessageText } from "@mail/utils/common/format";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";

patch(Store.prototype, {
    /**
     * @param {string} searchTerm
     * @param {import("models").Thread} thread
     * @param {number|false} before
     * @param {true|false|undefined} is_notification
     * @param {Object} [fetchParams] 
     */
    async searchMessagesInThread(searchTerm, thread, before, is_notification, fetchParams) {
        if (!fetchParams) {
            return super.searchMessagesInThread(...arguments);
        }
        const { count, data, messages } = await rpc(thread.getFetchRoute(), {
            ...thread.getFetchParams(),
            fetch_params: {
                ...fetchParams,
                is_notification,
                search_term: await prettifyMessageText(searchTerm),
                before,
            },
        });
        this.insert(data);
        return {
            count,
            loadMore: messages.length === this.FETCH_LIMIT,
            messages: this["mail.message"].insert(messages),
        };
    },
});
