import { useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { ControlPanel } from "@web/search/control_panel/control_panel";

import {
    closeSplit,
    isDirectionToggleEnabled,
    openSplit,
    setSplitActive,
    splitViewState,
    toggleSplitDirection,
} from "../../split_view/split_view_state";

patch(ControlPanel.prototype, {
    setup() {
        super.setup(...arguments);
        this.splitViewState = useState(splitViewState);
    },

    showSplitView() {
        return !!this.env.ipSplitAvailable && !this.env.inSplitView && !this.env.inDialog;
    },

    showSplitDirection() {
        return (
            this.showSplitView() &&
            splitViewState.active &&
            !!session.split_direction &&
            !this.env.isSmall
        );
    },

    get isSplitDirectionToggle() {
        return isDirectionToggleEnabled();
    },

    onSplitViewClicked() {
        if (session.default_split_view) {
            if (splitViewState.show) {
                closeSplit();
            } else if (splitViewState.previousResId) {
                openSplit(splitViewState.previousResModel, splitViewState.previousResId);
            }
            return;
        }
        setSplitActive(!splitViewState.active);
        this.env.services.notification.add(
            splitViewState.active ? _t("Split View Activated") : _t("Split View Deactivated"),
            {
                type: splitViewState.active ? "success" : "warning",
                title: _t("Split View"),
            }
        );
    },

    onSplitDirectionClicked() {
        toggleSplitDirection();
    },
});
