/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { KanbanRecord } from "@web/views/kanban/kanban_record";

import { splitViewState, isSplitEnabled } from "../split_view/split_view_state";

patch(KanbanRecord.prototype, {
    setup() {
        super.setup(...arguments);

        this.ipSplit = useState(splitViewState);
    },

    getRecordClasses() {
        let cls = super.getRecordClasses(...arguments);

        if (
            isSplitEnabled("kanban") &&
            this.env.config?.viewType === "kanban" &&
            !this.env.inSplitView &&
            this.ipSplit.show &&
            this.ipSplit.resId === this.props.record.resId
        ) {
            cls += " o_ipredict_split_selected";
        }

        return cls;
    },
});