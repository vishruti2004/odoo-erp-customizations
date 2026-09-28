/** @odoo-module **/

import { useService } from '@web/core/utils/hooks';
import { FormController } from '@web/views/form/form_controller';
import { usePager } from "@web/search/pager_hook";
import { SplitViewStatusIndicator } from "./split_view_components";
import {
    executeBeforeSplitViewOpen,
    registerBeforeSplitViewOpen,
    unregisterBeforeSplitViewOpen,
} from "./split_view_components";
import { onMounted, onWillDestroy } from '@odoo/owl';

/**
 * SplitViewController - Custom FormController for split view
 * Provides pager navigation, auto-save hooks, and customized UI for split view mode
 */
export class SplitViewController extends FormController {
    static template = 'split_view.SplitViewForm';
    static components = {
        ...FormController.components,
        SplitViewStatusIndicator,
    };

    static props = {
        ...FormController.props,
        onUpdate: {
            type: Function,
            optional: true,
        },
    };

    setup() {
        super.setup();

        // Hide view switcher entries in split view
        this.env.config.viewSwitcherEntries = [];
        this.env.config.pagerProps = null;

        this.actionService = useService('action');

        // Register auto-save function for before split view open
        this.saveFunction = this.saveButtonClicked.bind(this);
        registerBeforeSplitViewOpen(this.saveFunction);

        // Setup pager for record navigation
        usePager(() => {
            if (!this.model.root.isVirtual) {
                const resIds = this.props.resIds;
                return {
                    offset: resIds.indexOf(this.props.resId),
                    limit: 1,
                    total: resIds.length,
                    onUpdate: ({ offset }) => this.onPagerUpdate({
                        offset,
                        resIds
                    }),
                };
            }
        });

        onMounted(() => this._onMounted());
        onWillDestroy(() => {
            unregisterBeforeSplitViewOpen(this.saveFunction);
        });
    }

    /**
     * Called when component is mounted
     * Hides unnecessary UI elements.
     * Scoped to the split panel and matched on semantic classes only: chaining
     * Bootstrap utility classes into the selector breaks on any core restyling.
     * The breadcrumbs and the view switcher are already hidden by split_view.scss.
     */
    _onMounted() {
        // Hide pager in form view container
        const pager = document.querySelector('.split_view_panel .o_cp_pager');
        if (pager) {
            pager.style.display = 'none';
        }
    }

    /**
     * Handle pager navigation updates
     * @param {Object} params - Pager params
     * @param {number} params.offset - New offset
     * @param {Array} params.resIds - Record IDs
     */
    async onPagerUpdate({ offset, resIds }) {
        await this.model._askChanges();
        let canProceed = true;

        // Auto-save if dirty
        if (this.model.root.dirty) {
            canProceed = await this.model.root.save({
                stayInEdition: true,
                useSaveErrorDialog: true,
            });
        }

        if (canProceed) {
            return this.model.load({
                resId: resIds[offset]
            });
        }
    }

    /**
     * Override save to trigger update callback
     */
    async save() {
        const changedFields = await super.save();
        if (this.props.onUpdate) {
            this.props.onUpdate();
        }
        return changedFields;
    }

    /**
     * Override to highlight selected row in list
     */
    getActionMenuItems() {
        const actionMenuItems = super.getActionMenuItems(...arguments);

        // Highlight the selected row in list view
        const listRows = document.querySelectorAll('.o_list_renderer .o_data_row');
        listRows.forEach(row => {
            row.classList.remove('split_view_selected', 'active');
            if (row.getAttribute('data-id') === String(this.props.resId) ||
                row.querySelector(`[data-id="${this.props.resId}"]`)) {
                row.classList.add('split_view_selected', 'active');
            }
        });

        return actionMenuItems;
    }
}
