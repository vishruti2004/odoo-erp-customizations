/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";

import {
    splitViewState,
    isSplitEnabled,
    isNewSplitEnabled,
    openSplit,
} from "../split_view/split_view_state";

import { hasFormView } from "../../utils/split_view_utils";

patch(ListController.prototype, {
    async createRecord(params = {}) {
        if (
            this.editable ||
            !isNewSplitEnabled() ||
            !splitViewState.gate ||
            !splitViewState.active ||
            !isSplitEnabled("list") ||
            !hasFormView(this.env) ||
            this.env.inSplitView ||
            this.env.inDialog ||
            this.env.isSmall
        ) {
            return super.createRecord(...arguments);
        }

        openSplit(this.props.resModel, false);
    },
});