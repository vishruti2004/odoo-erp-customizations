/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";

import {
    splitViewState,
    notifyHostRefreshed,
} from "../split_view/split_view_state";

function isRelevantHost(controller) {
    return (
        splitViewState.show &&
        splitViewState.resModel === controller.model.root.resModel &&
        !controller.env.inSplitView &&
        !controller.env.inDialog &&
        !controller.env.isSmall
    );
}

patch(ListController.prototype, {
    // "Actions" (cog) menu on selected records: Export/Duplicate/Delete/
    // Cancel/etc.
    get actionMenuProps() {
        const props = super.actionMenuProps;

        return {
            ...props,
            onActionExecuted: async (...args) => {
                const result = await props.onActionExecuted(...args);

                if (isRelevantHost(this)) {
                    notifyHostRefreshed();
                }

                return result;
            },
        };
    },

    // Header / statusbar contextual buttons (e.g. the "Cancel" button that
    // appears above the list when quotations are selected).
    async afterExecuteActionButton(clickParams) {
        const result = await super.afterExecuteActionButton(clickParams);

        if (isRelevantHost(this)) {
            notifyHostRefreshed();
        }

        return result;
    },
});