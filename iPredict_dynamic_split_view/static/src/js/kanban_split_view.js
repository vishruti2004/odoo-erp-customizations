/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { splitViewState, isSplitEnabled, openSplit } from "./split_view_state";

patch(KanbanController.prototype, {
    get isSplitHost() {
        return (
            isSplitEnabled("kanban") &&
            this.env.config?.viewType === "kanban" &&
            !this.env.inSplitView &&
            !this.env.inDialog &&
            !this.env.isSmall
        );
    },

    async openRecord(record, options = {}) {
        if (
            !this.isSplitHost ||
            !splitViewState.active ||
            !record?.resId ||
            options.newWindow 
        ) {
            return super.openRecord(...arguments);
        }
        openSplit(record.resModel, record.resId);
    },
});

patch(KanbanRecord.prototype, {
    setup() {
        super.setup(...arguments);
        this.ipSplit = useState(splitViewState);
    },

    getRecordClasses() {
        let cls = super.getRecordClasses(...arguments);
        if (
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