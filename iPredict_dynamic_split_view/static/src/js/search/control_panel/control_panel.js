/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { session } from "@web/session";
import { ControlPanel } from "@web/search/control_panel/control_panel";

import {
    splitViewState,
    isSplitEnabled,
    setSplitActive,
    setSplitGate,
    toggleSplitDirection,
    isDirectionToggleEnabled,
    openSplit,
    closeSplit,
} from "../../views/split_view/split_view_state";

import { hasFormView } from "../../utils/split_view_utils";

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);

        this.splitViewState = useState(splitViewState);
    },

    showSplitGate() {
        return (
            session.enable_split_view &&
            isSplitEnabled(this.env.config?.viewType) &&
            hasFormView(this.env) &&
            !this.env.inSplitView &&
            !this.env.inDialog &&
            !this.env.isSmall
        );
    },

    showSplitView() {
        return (
            this.showSplitGate() &&
            splitViewState.gate
        );
    },

    showSplitDirection() {
        return (
            this.showSplitView() &&
            splitViewState.active &&
            !!session.split_direction
        );
    },

    get splitDirection() {
        return session.split_direction || "horizontal";
    },

    get isSplitDirectionToggle() {
        return session.split_direction === "both";
    },

    onSplitGateClicked() {
        setSplitGate(!splitViewState.gate);
    },

    onSplitViewClicked() {
        if (session.default_split_view) {
            if (splitViewState.show) {
                closeSplit();
            } else if (splitViewState.previousResId) {
                openSplit(
                    splitViewState.previousResModel,
                    splitViewState.previousResId
                );
            }

            return;
        }

        setSplitActive(!splitViewState.active);

        this.env.services.notification.add(
            splitViewState.active
                ? "Split View Activated"
                : "Split View Deactivated",
            {
                type: splitViewState.active
                    ? "success"
                    : "warning",
                title: "Split View",
            }
        );
    },

    onSplitDirectionClicked() {
        if (!isDirectionToggleEnabled()) {
            return;
        }

        toggleSplitDirection();
    },
});