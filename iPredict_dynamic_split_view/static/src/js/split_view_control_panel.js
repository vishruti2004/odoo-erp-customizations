/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { splitViewState, isSplitEnabled, setSplitActive } from "./split_view_state";

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);
        this.splitViewState = useState(splitViewState);
    },

    showSplitView() {
        return (
            isSplitEnabled(this.env.config?.viewType) &&
            !this.env.inSplitView &&
            !this.env.inDialog &&
            !this.env.isSmall
        );
    },

    onSplitViewClicked() {
        setSplitActive(!splitViewState.active);
        this.env.services.notification.add(
            splitViewState.active ? "Split View Activated" : "Split View Deactivated",
            { type: splitViewState.active ? "success" : "warning", title: "Split View" }
        );
    },
});