/** @odoo-module **/

import { executeBeforeSplitViewOpen } from "./split_view_components";

/**
 * Behaviour shared by the ListRenderer and KanbanRenderer split view patches.
 * Spread it into each patch(); the renderer-specific parts stay in the patches:
 *
 *  - _resetSplitViewLayout()    undo the inline sizing left by the separator
 *  - _clearSplitViewSelection() drop the highlight from rows / cards
 *
 * None of these methods call super, so spreading them into a patch object
 * literal is safe.
 */
export const splitViewRendererMixin = {
    /**
     * Get the form view ID from config
     * @returns {number|false} - Form view ID or false
     */
    _getFormViewId() {
        const views = this.env.config.views || [];
        const formView = views.find((view) => view[1] === "form");
        return formView ? formView[0] : false;
    },

    /**
     * Check if split view mode is active
     * @returns {boolean}
     */
    _isSplitViewActive() {
        return document.body.classList.contains("split_view_active");
    },

    /**
     * Execute all registered hooks before opening split view
     * @returns {Promise}
     */
    async _executeBeforeSplitViewOpen() {
        return executeBeforeSplitViewOpen();
    },

    /**
     * Get props for the SplitviewContainer component
     * @returns {Object} - Container props
     */
    getSplitviewContainerProps() {
//         console.log(">>> SPLIT CONTAINER PROPS CALLED");
// console.log("MODEL:", this.props.list?.resModel);
// console.log("RENDERER:", this.constructor.name);
// console.log("STATE:", this.splitViewState);
        const list = this.props.list;
        if (!list) {
            return {};
        }

        // `records` is already flattened across unfolded groups on grouped
        // lists, so this covers both grouped and ungrouped renderers.
        const resIds = (list.records || []).map((record) => record.resId);

        const props = {
            context: this._splitViewRecord ? { ...this._splitViewRecord.context } : {},
            record: this._splitViewRecord,
            resModel: list.resModel,
            resId: this.splitViewState.resId,
            resIds: resIds,
            onUpdate: () => {
                if (this._splitViewRecord) {
                    this._splitViewRecord.load();
                }
            },
        };

        const viewId = this._getFormViewId();
        if (viewId) {
            props.viewId = viewId;
        }

        return props;
    },

    /**
     * Close the split view form panel.
     * The separator is rendered by SplitviewContainer, so unmounting the
     * container removes it — no manual DOM cleanup needed here.
     */
    async _closeSplitView() {
        // Execute pre-close hooks. The SplitViewController unregisters its own
        // hook in onWillDestroy, so we must not clear the shared registry.
        await this._executeBeforeSplitViewOpen();

        this.splitViewState.show = false;
        this.splitViewState.resId = 0;
        this._splitViewRecord = null;

        this._resetSplitViewLayout();
        this._clearSplitViewSelection();
    },
};
