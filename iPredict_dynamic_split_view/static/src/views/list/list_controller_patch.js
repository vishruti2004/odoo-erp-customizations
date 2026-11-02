import { useSubEnv } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import {
    hasFormView,
    isNewSplitEnabled,
    isSplitEnabled,
    notifyHostRefreshed,
    openSplit,
    splitViewState,
} from "../../split_view/split_view_state";

patch(ListController.prototype, {
    setup() {
        super.setup(...arguments);
        useSubEnv({ ipSplitAvailable: this.isSplitHost });
    },

    get isSplitHost() {
        return (
            isSplitEnabled("list") &&
            hasFormView(this.env) &&
            this.env.config?.viewType === "list" &&
            !this.env.inSplitView &&
            !this.env.inDialog &&
            !this.editable &&
            !this.archInfo.noOpen &&
            !(this.props.allowOpenAction && this.archInfo.openAction)
        );
    },
    async openRecord(record, options = {}) {
        if (
            !this.isSplitHost ||
            !splitViewState.active ||
            !record.resId ||
            options.newWindow
        ) {
            return super.openRecord(...arguments);
        }
        if (await record.isDirty()) {
            await record.save();
        }
        openSplit(record.resModel, record.resId);
    },

    async createRecord() {
        if (this.editable || !isNewSplitEnabled() || !splitViewState.active || !this.isSplitHost) {
            return super.createRecord(...arguments);
        }
        openSplit(this.props.resModel, false);
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
