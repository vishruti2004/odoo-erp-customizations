import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";

import {
    closeSplit,
    notifySplitSaved,
    openSplit,
    splitViewState,
} from "../../split_view/split_view_state";

patch(FormController.prototype, {
    async onRecordSaved(record, changes) {
        const result = await super.onRecordSaved(...arguments);
        if (this.env.inSplitView) {
            notifySplitSaved();
        }
        return result;
    },

    async discard() {
        if (this.env.inSplitView && !this.model.root.resId) {
            const result = await super.discard(...arguments);
            if (splitViewState.previousResId) {
                openSplit(splitViewState.previousResModel, splitViewState.previousResId);
            } else {
                closeSplit();
            }
            return result;
        }
        return super.discard(...arguments);
    },
});
