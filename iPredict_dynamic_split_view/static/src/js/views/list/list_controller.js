/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";

import {
    splitViewState,
    isSplitEnabled,
    isNewSplitEnabled,
    openSplit,
    notifyHostRefreshed,
} from "../split_view/split_view_state";

import { hasFormView } from "../../utils/split_view_utils";

patch(ListController.prototype, {
    async createRecord(params = {}) {
        if (
            isNewSplitEnabled() &&
            splitViewState.gate &&
            splitViewState.active &&
            isSplitEnabled("list") &&
            hasFormView(this.env) &&
            !this.env.inSplitView &&
            !this.env.inDialog &&
            !this.env.isSmall
        ) {
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
                const result =
                    await props.onActionExecuted(...args);

                if (
                    splitViewState.show &&
                    splitViewState.resModel ===
                        this.model.root.resModel
                ) {
                    notifyHostRefreshed();
                }

                return result;
            },
        };
    },
});