import { useEffect, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

import { splitViewState } from "../../split_view/split_view_state";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.ipSplit = useState(splitViewState);

        let isFirstRun = true;
        useEffect(
            () => {
                if (isFirstRun) {
                    isFirstRun = false;
                    return;
                }
                if (this.isSplitHost) {
                    this.props.list.model.load();
                }
            },
            () => [this.ipSplit.syncTick]
        );
    },

    get isSplitHost() {
        return !!this.env.ipSplitAvailable && !this.isX2Many && !this.env.inSplitView;
    },

    getRowClass(record) {
        let cls = super.getRowClass(...arguments);
        if (this.isSplitHost && this.ipSplit.show && this.ipSplit.resId === record.resId) {
            cls += " o_ipredict_split_selected";
        }
        return cls;
    },
});
