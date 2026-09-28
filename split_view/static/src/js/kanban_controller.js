/** @odoo-module **/

import { KanbanController } from "@web/views/kanban/kanban_controller";
import { patch } from "@web/core/utils/patch";

/**
 * Patch KanbanController to intercept record opening when in split view mode
 */
patch(KanbanController.prototype, {
    /**
     * @override
     */
    openRecord(record, mode) {
        // Check if split view is currently active
        const isSplitViewActive = document.body.classList.contains('split_view_active');

        if (!isSplitViewActive) {
            super.openRecord(record, mode);
            return;
        }

        // Trigger event for renderer to handle
        this.env.bus.trigger('split-view-open-record', { record, mode });
    }
});
