/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useEffect, useState } from "@odoo/owl";
import { KanbanController } from "@web/views/kanban/kanban_controller";

import {
    splitViewState,
    isSplitEnabled,
    isNewSplitEnabled,
    openSplit,
} from "../split_view/split_view_state";

import { hasFormView } from "../../utils/split_view_utils";

patch(KanbanController.prototype, {
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
                    this.model.load();
                }
            },
            () => [this.ipSplit.syncTick]
        );
    },

    get isSplitHost() {
        return (
            isSplitEnabled("kanban") &&
            hasFormView(this.env) &&
            this.env.config?.viewType === "kanban" &&
            !this.env.inSplitView &&
            !this.env.inDialog
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

    async createRecord(params = {}) {
        if (
            isNewSplitEnabled() &&
            splitViewState.gate &&
            splitViewState.active &&
            this.isSplitHost
        ) {
            openSplit(this.props.resModel, false);
            return;
        }

        return super.createRecord(...arguments);
    },
});