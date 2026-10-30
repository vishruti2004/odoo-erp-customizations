/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { KanbanController } from "@web/views/kanban/kanban_controller";

import {
    splitViewState,
    notifyHostRefreshed,
} from "../split_view/split_view_state";

function isRelevantHost(controller) {
    return (
        splitViewState.show &&
        splitViewState.resModel === controller.model.root.resModel &&
        !controller.env.inSplitView &&
        !controller.env.inDialog
    );
}

patch(KanbanController.prototype, {
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

    async afterExecuteActionButton(clickParams) {
        const result = await super.afterExecuteActionButton(clickParams);

        if (isRelevantHost(this)) {
            notifyHostRefreshed();
        }

        return result;
    },
});