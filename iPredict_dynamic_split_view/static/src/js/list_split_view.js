/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";
import { splitViewState, isSplitEnabled, openSplit } from "./split_view_state";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.ipSplit = useState(splitViewState);
    },

    get isSplitHost() {
        return (
            isSplitEnabled("list") &&
            !this.isX2Many &&
            this.env.config?.viewType === "list" &&
            !this.env.inSplitView &&
            !this.env.inDialog &&
            !this.uiService.isSmall
        );
    },

    async onCellClicked(record, column, ev) {
        if (!this.isSplitHost || !this.ipSplit.active || !record?.resId || ev.target.special_click) {
            return super.onCellClicked(...arguments);
        }
        openSplit(record.resModel, record.resId);
    },

    getRowClass(record) {
        let cls = super.getRowClass(...arguments);
        if (this.isSplitHost && this.ipSplit.show && this.ipSplit.resId === record.resId) {
            cls += " o_ipredict_split_selected";
        }
        return cls;
    },
});