/** @odoo-module **/

import { ControlPanel } from "@web/search/control_panel/control_panel";
import { patch } from "@web/core/utils/patch";
import { onMounted, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const STORAGE_KEY = 'odoo_split_view';

/**
 * Patch ControlPanel to add split view toggle button
 */
patch(ControlPanel.prototype, {
    setup() {
        super.setup();

        this.notificationService = useService("notification");

        // Reactive state: the template binds the `active` class to it, so the
        // button survives re-renders without any direct DOM manipulation.
        this.splitView = useState({ active: false });
        this._splitViewKey = this._getSplitViewKey();

        onMounted(() => {
            this._initSplitView();
        });
    },

    /**
     * Restore the split view state saved for this action
     */
    _initSplitView() {
        if (!this.showSplitView()) {
            return;
        }

        const config = this._getSplitViewConfig();
        this._applySplitViewState(Boolean(config[this._splitViewKey]));
    },

    /**
     * Check if split view button should be shown
     * Only show in list and kanban views
     * @returns {boolean}
     */
    showSplitView() {
        const viewType = this.env.config?.viewType;
        return viewType === 'list' || viewType === 'kanban';
    },

    /**
     * Apply a split view state to both the button and the renderers, which
     * read the body class to decide how to handle record clicks.
     * @param {boolean} isActive
     */
    _applySplitViewState(isActive) {
        this.splitView.active = isActive;
        document.body.classList.toggle('split_view_active', isActive);
    },

    /**
     * Handle split view toggle button click
     */
    onSplitViewClicked() {
        // Close any open split view form first
        const closeBtn = document.querySelector('.btn-split-close');
        if (closeBtn) {
            closeBtn.click();
        }

        const isActive = !this.splitView.active;
        this._applySplitViewState(isActive);

        // Save preference to localStorage
        const config = this._getSplitViewConfig();
        config[this._splitViewKey] = isActive;
        browser.localStorage.setItem(STORAGE_KEY, JSON.stringify(config));

        // Show notification
        this.notificationService.add(
            isActive ? _t("Split View activated") : _t("Split View deactivated"),
            { type: "info" }
        );
    },

    /**
     * Generate a unique key for the current view, based on model and action.
     * Both come from the view config: Odoo 19 uses path-based URLs
     * (/odoo/action-123/45), so the legacy hash query string is always empty.
     * @returns {string}
     */
    _getSplitViewKey() {
        const model = this.env.searchModel?.resModel;
        const action = this.env.config?.actionId || this.env.config?.actionXmlId;

        return `${model || 'unknown'}.${action || 'unknown'}`;
    },

    /**
     * Get split view configuration from localStorage
     * @returns {Object}
     */
    _getSplitViewConfig() {
        const data = browser.localStorage.getItem(STORAGE_KEY);
        try {
            return data ? JSON.parse(data) : {};
        } catch (e) {
            return {};
        }
    },
});
