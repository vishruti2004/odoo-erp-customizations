/** @odoo-module **/

import { FormStatusIndicator } from '@web/views/form/form_status_indicator/form_status_indicator';
import { WithSearch, SEARCH_KEYS } from '@web/search/with_search/with_search';

// Extend WithSearch to support resId prop
SEARCH_KEYS.push('resId');
WithSearch.props.resId = {
    type: [Number, { value: null }, { value: false }],
    optional: true
};

/**
 * SplitViewStatusIndicator - Status indicator for split view form
 * Shows save/discard buttons when form is dirty
 */
export class SplitViewStatusIndicator extends FormStatusIndicator {
    static template = 'split_view.SplitViewStatusIndicator';
}

/**
 * Hook registry for actions to execute before opening a new record in split view
 * Used primarily for auto-save functionality
 */
export const beforeSplitViewOpen = [];

/**
 * Register a function to be called before opening a record in split view
 * @param {Function} func - Function to execute (should return a Promise)
 */
export function registerBeforeSplitViewOpen(func) {
    if (typeof func === 'function' && !beforeSplitViewOpen.includes(func)) {
        beforeSplitViewOpen.push(func);
    }
}

/**
 * Unregister a function from the before split view open hooks
 * @param {Function} func - Function to remove
 */
export function unregisterBeforeSplitViewOpen(func) {
    const index = beforeSplitViewOpen.indexOf(func);
    if (index !== -1) {
        beforeSplitViewOpen.splice(index, 1);
    }
}

/**
 * Clear all registered hooks
 */
export function clearBeforeSplitViewOpen() {
    beforeSplitViewOpen.length = 0;
}

/**
 * Execute all registered hooks
 * @returns {Promise} - Resolves when all hooks complete
 */
export async function executeBeforeSplitViewOpen() {
    const results = [];
    for (const func of beforeSplitViewOpen) {
        try {
            results.push(await func());
        } catch (e) {
            console.warn('Error in beforeSplitViewOpen hook:', e);
        }
    }
    return results;
}

