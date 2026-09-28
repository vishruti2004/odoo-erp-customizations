/** @odoo-module **/
import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";

const KEY = "ipredict_split_view_active";

export const splitViewState = reactive({
    active: browser.localStorage.getItem(KEY) === "1",
    show: false,
    resId: null,
    resModel: null,
});

// Button / split only for the view types enabled in Settings
export function isSplitEnabled(viewType) {
    if (viewType === "list") {
        return !!session.enable_list_split_view;
    }
    if (viewType === "kanban") {
        return !!session.enable_kanban_split_view;
    }
    return false;
}

export function openSplit(resModel, resId) {
    splitViewState.resModel = resModel;
    splitViewState.resId = resId;
    splitViewState.show = true;
}

export function closeSplit() {
    splitViewState.show = false;
    splitViewState.resId = null;
    splitViewState.resModel = null;
}

export function setSplitActive(value) {
    splitViewState.active = value;
    browser.localStorage.setItem(KEY, value ? "1" : "0");
    if (!value) {
        closeSplit();
    }
}