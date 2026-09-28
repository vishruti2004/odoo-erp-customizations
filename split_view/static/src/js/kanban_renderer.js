/** @odoo-module **/

import { SplitviewContainer } from "./split_view_container";
import { splitViewRendererMixin } from "./split_view_renderer_mixin";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { patch } from "@web/core/utils/patch";
import { useChildSubEnv, useState, onWillDestroy } from "@odoo/owl";

/**
 * Patch KanbanRenderer to support split view functionality
 * Adds click handling to open records in side panel instead of navigating
 */
patch(KanbanRenderer.prototype, {
    ...splitViewRendererMixin,

    setup() {
        super.setup();

        // State for split view form panel
        this.splitViewState = useState({
            show: false,
            resId: 0,
        });

        // Current record being displayed in split view
        this._splitViewRecord = null;

        // Get form view ID for split view
        const formViewId = this._getFormViewId();

        // Provide split view config to child components
        useChildSubEnv({
            config: {
                ...this.env.config,
                views: [[formViewId, 'form']],
                close: this._closeSplitView.bind(this),
            },
        });

        // Listen for split view open event from controller
        this._onSplitViewOpenRecord = this._onSplitViewOpenRecord.bind(this);
        this.env.bus.addEventListener('split-view-open-record', this._onSplitViewOpenRecord);

        onWillDestroy(() => {
            this.env.bus.removeEventListener('split-view-open-record', this._onSplitViewOpenRecord);
        });
    },

    /**
     * Handler for split-view-open-record event
     */
    async _onSplitViewOpenRecord({ detail }) {
        const { record, mode } = detail;
        await this.openRecordInSplitView(record, { mode });
    },

    /**
     * Custom openRecord handler for split view
     * @param {Object} record - Record to open
     * @param {Object} options - Open options
     */
    async openRecordInSplitView(record, options = {}) {
        const isSplitViewActive = this._isSplitViewActive();

        if (!isSplitViewActive || options.newWindow) {
            // Use default behavior - call original openRecord
            return this.props.openRecord(record, options);
        }

        // Open record in split view if it's not shown OR it's a different record
        if (record.resId && (!this.splitViewState.show || this.splitViewState.resId !== record.resId)) {
            // Execute pre-open hooks (e.g., auto-save)
            await this._executeBeforeSplitViewOpen();

            // Update state
            this.splitViewState.resId = record.resId;
            this.splitViewState.show = true;
            this._splitViewRecord = record;

            // Highlight selected card
            this._highlightSelectedCard(record);
        }
    },

    /**
     * Highlight the selected card in the kanban
     * @param {Object} record - Selected record
     */
    _highlightSelectedCard(record) {
        const rootEl = this.rootRef.el;
        if (!rootEl) return;

        this._clearSplitViewSelection();

        // Add selection to current card
        const selectedCard = rootEl.querySelector(`[data-id="${CSS.escape(record.id)}"]`);
        if (selectedCard) {
            selectedCard.classList.add('split_view_selected');
        }
    },

    /**
     * Remove the split view highlight from every card
     */
    _clearSplitViewSelection() {
        const rootEl = this.rootRef.el;
        if (!rootEl) return;

        rootEl.querySelectorAll('.o_kanban_record').forEach(card => {
            card.classList.remove('split_view_selected');
        });
    },

    /**
     * Undo the inline sizing applied while dragging the separator
     */
    _resetSplitViewLayout() {
        const kanbanRenderer = this.rootRef.el;
        if (kanbanRenderer) {
            kanbanRenderer.style.width = '';
            kanbanRenderer.style.minWidth = '';
            kanbanRenderer.style.maxWidth = '';
            kanbanRenderer.style.flexShrink = '';
        }
    },
});

// Register SplitviewContainer component
KanbanRenderer.components = {
    ...KanbanRenderer.components,
    SplitviewContainer,
};
