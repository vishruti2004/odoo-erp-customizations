/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useEffect, useState } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";

import {
    splitViewState,
    isSplitEnabled,
    openSplit,
} from "../split_view/split_view_state";

import { hasFormView } from "../../utils/split_view_utils";

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
        return (
            isSplitEnabled("list") &&
            hasFormView(this.env) &&
            !this.isX2Many &&
            this.env.config?.viewType === "list" &&
            !this.env.inSplitView &&
            !this.env.inDialog
        );
    },

    async onCellClicked(record, column, ev) {
        if (
            !this.isSplitHost ||
            !this.ipSplit.active ||
            !record?.resId ||
            ev.target.special_click
        ) {
            return super.onCellClicked(...arguments);
        }

        openSplit(record.resModel, record.resId);
    },

    getRowClass(record) {
        let cls = super.getRowClass(...arguments);

        if (
            this.isSplitHost &&
            this.ipSplit.show &&
            this.ipSplit.resId === record.resId
        ) {
            cls += " o_ipredict_split_selected";
        }

        return cls;
    },
});