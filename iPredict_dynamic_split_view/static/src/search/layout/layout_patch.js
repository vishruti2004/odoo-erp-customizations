import { onWillUnmount, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { Layout } from "@web/search/layout";

import { SplitViewContainer } from "../../split_view/split_view_container";
import { closeSplit, splitViewState } from "../../split_view/split_view_state";

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
        return !!this.env.ipSplitAvailable && !this.env.inSplitView && !this.env.inDialog;
    },

    get ipSplitContainer() {
        return SplitViewContainer;
    },

    get ipSplitShow() {
        if (
            !this.ipSplitHost ||
            !this.ipSplit.active ||
            !this.ipSplit.show ||
            !this.ipSplit.resModel
        ) {
            return false;
        }
        const model = this.env.searchModel?.resModel;
        return !model || model === this.ipSplit.resModel;
    },

    get ipSplitProps() {
        return {
            resModel: this.ipSplit.resModel,
            resId: this.ipSplit.resId,
        };
    },
});
