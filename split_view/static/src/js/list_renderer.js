/** @odoo-module **/

import { SplitviewContainer } from "./split_view_container";
import { splitViewRendererMixin } from "./split_view_renderer_mixin";
import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";
import { useChildSubEnv, useState } from "@odoo/owl";

/**
 * Patch ListRenderer to support split view functionality
 * Adds click handling to open records in side panel instead of navigating
 */
patch(ListRenderer.prototype, {
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
                isX2Many: this.isX2Many,
                views: [[formViewId, 'form']],
                close: this._closeSplitView.bind(this),
            },
        });
    },

    /**
     * Override cell click handler for split view functionality
     * @param {Object} record - Clicked record
     * @param {Object} column - Clicked column
     * @param {Event} ev - Click event
     */
    async onCellClicked(record, column, ev) {
        console.log("========== SPLIT DEBUG ==========");
console.log("MODEL:", this.props.list.resModel);
console.log("RENDERER:", this.constructor.name);
console.log("SPLIT ACTIVE:", this._isSplitViewActive());
console.log("RECORD ID:", record.resId);
        console.log("SPLIT click", record.resId, this._isSplitViewActive(), this.isX2Many);
        const isSplitViewActive = this._isSplitViewActive();
        const isEditable = this.props.archInfo?.editable;
        const hasSplitViewAttr = this.props.archInfo?.splitView;

        // Determine if we should use split view behavior
        const useSplitView = (
            (!this.isX2Many && isSplitViewActive) ||
            (this.isX2Many && hasSplitViewAttr)
        ) && !isEditable;

        if (!useSplitView) {
            // Use default behavior
            return super.onCellClicked(record, column, ev);
        }

        // Check for special click (e.g., checkbox, button)
        if (ev.target.special_click) {
            return;
        }

        // Open record in split view if it's a different record
        if (record.resId && this.splitViewState.resId !== record.resId && !isEditable) {
            // Execute pre-open hooks (e.g., auto-save)
            await this._executeBeforeSplitViewOpen();

            // Update state
console.log(">>> SPLIT CONDITION PASSED");

console.log("BEFORE STATE:", {
    resId: this.splitViewState.resId,
    show: this.splitViewState.show,
});

this.splitViewState.resId = record.resId;
this.splitViewState.show = true;

console.log("AFTER STATE:", {
    resId: this.splitViewState.resId,
    show: this.splitViewState.show,
});

this._splitViewRecord = record;

            // Highlight selected row
            this._highlightSelectedRow(record);
        }
    },

    /**
     * Highlight the selected row in the list
     * @param {Object} record - Selected record
     */
    _highlightSelectedRow(record) {
        const table = this.tableRef.el;
        if (!table) return;

        this._clearSplitViewSelection();

        // Add selection to current row
        const selectedRow = table.querySelector(`tr[data-id="${CSS.escape(record.id)}"]`);
        if (selectedRow) {
            selectedRow.classList.add('active', 'split_view_selected');
        }
    },

    /**
     * Remove the split view highlight from every row
     */
    _clearSplitViewSelection() {
        const table = this.tableRef.el;
        if (!table) return;

        table.querySelectorAll('.o_data_row').forEach(row => {
            row.classList.remove('active', 'split_view_selected');
        });
    },

    /**
     * Undo the inline sizing applied while dragging the separator
     */
    _resetSplitViewLayout() {
        // The wrapper is what gets resized, but clear the renderer too in case
        // an older version of the module left inline styles behind.
        const elements = [
            this.tableRef.el?.closest('.split_view_list_wrapper'),
            this.tableRef.el?.closest('.o_list_renderer'),
        ];

        for (const el of elements) {
            if (el) {
                el.style.width = '';
                el.style.minWidth = '';
                el.style.maxWidth = '';
                el.style.flexShrink = '';
            }
        }
    },
});

// Register SplitviewContainer component
ListRenderer.components = {
    ...ListRenderer.components,
    SplitviewContainer,
};
