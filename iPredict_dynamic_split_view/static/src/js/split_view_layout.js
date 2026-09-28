/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { onWillUnmount, useState } from "@odoo/owl";
import { Layout } from "@web/search/layout";
import { SplitViewContainer } from "./split_view_container";
import { splitViewState, isSplitEnabled, closeSplit } from "./split_view_state";

patch(Layout.prototype, {
    setup() {
        super.setup(...arguments);
        this.ipSplit = useState(splitViewState);
        onWillUnmount(() => {
            if (this.ipSplitHost) {
                closeSplit();
            }
        });
    },

    get ipSplitHost() {
        return (
            isSplitEnabled(this.env.config?.viewType) &&
            !this.env.inSplitView &&
            !this.env.inDialog &&
            !this.env.isSmall
        );
    },

    get ipSplitContainer() {
        return SplitViewContainer;
    },

    get ipSplitShow() {
        if (!this.ipSplitHost || !this.ipSplit.active || !this.ipSplit.show || !this.ipSplit.resId) {
            return false;
        }
        const model = this.env.searchModel?.resModel;
        return !model || model === this.ipSplit.resModel;
    },

    get ipSplitProps() {
        return { resModel: this.ipSplit.resModel, resId: this.ipSplit.resId };
    },
});