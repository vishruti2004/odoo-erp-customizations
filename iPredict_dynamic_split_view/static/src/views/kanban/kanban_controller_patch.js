import { useEffect, useState, useSubEnv } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";

import {
    hasFormView,
    isNewSplitEnabled,
    isSplitEnabled,
    notifyHostRefreshed,
    openSplit,
    splitViewState,
} from "../../split_view/split_view_state";

patch(KanbanController.prototype, {
    setup() {
        super.setup(...arguments);
        this.ipSplit = useState(splitViewState);
        useSubEnv({ ipSplitAvailable: this.isSplitHost });

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
            !this.env.inDialog &&
            this.props.archInfo.canOpenRecords &&
            !this.props.archInfo.openAction
        );
    },

    async openRecord(record, options = {}) {
        if (!this.isSplitHost || !splitViewState.active || !record?.resId || options.newWindow) {
            return super.openRecord(...arguments);
        }
        openSplit(record.resModel, record.resId);
    },

    async createRecord() {
        if (isNewSplitEnabled() && splitViewState.active && this.isSplitHost) {
            openSplit(this.props.resModel, false);
            return;
        }
        return super.createRecord(...arguments);
    },

    get actionMenuProps() {
        const props = super.actionMenuProps;
        return {
            ...props,
            onActionExecuted: async (...args) => {
                const result = await props.onActionExecuted(...args);
                this._notifySplitHostRefreshed();
                return result;
            },
        };
    },

    async afterExecuteActionButton(clickParams) {
        const result = await super.afterExecuteActionButton(clickParams);
        this._notifySplitHostRefreshed();
        return result;
    },

    _notifySplitHostRefreshed() {
        if (
            splitViewState.show &&
            splitViewState.resModel === this.model.root.resModel &&
            !this.env.inSplitView &&
            !this.env.inDialog
        ) {
            notifyHostRefreshed();
        }
    },
});
