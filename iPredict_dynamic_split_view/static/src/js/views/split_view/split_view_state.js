/** @odoo-module **/

import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";

const ACTIVE_KEY = "ipredict_split_view_active";
const GATE_KEY = "ipredict_split_view_gate";
const DIRECTION_KEY = "ipredict_split_view_direction";

const defaultSplitView = !!session.default_split_view;

const configuredDirection =
    session.split_direction || "horizontal";

const storedDirection =
    browser.localStorage.getItem(DIRECTION_KEY);

const defaultDirection =
    configuredDirection === "both"
        ? (storedDirection || "horizontal")
        : configuredDirection;

export const splitViewState = reactive({
    gate: true,

    active:
        defaultSplitView ||
        browser.localStorage.getItem(ACTIVE_KEY) === "1",

    direction: defaultDirection,

    show: false,

    resId: false,
    resModel: null,

    previousResModel: null,
    previousResId: false,

    syncTick: 0,
    hostRefreshTick: 0,
});

export function isSplitEnabled(viewType) {
    if (!session.enable_split_view || !session.enable_split_view_type) {
        return false;
    }

    if (viewType === "list") {
        return !!session.enable_list_split_view;
    }

    if (viewType === "kanban") {
        return !!session.enable_kanban_split_view;
    }

    return false;
}

export function isNewSplitEnabled() {
    return !!session.enable_new_split_view;
}

export function isDirectionToggleEnabled() {
    return session.split_direction === "both";
}

export function openSplit(resModel, resId = false) {
    if (resId === false && splitViewState.resId) {
        splitViewState.previousResModel = splitViewState.resModel;
        splitViewState.previousResId = splitViewState.resId;
    } else if (resId !== false) {
        splitViewState.previousResModel = null;
        splitViewState.previousResId = false;
    }

    splitViewState.resModel = resModel;
    splitViewState.resId = resId;
    splitViewState.show = true;
}

export function closeSplit() {
    splitViewState.show = false;
    splitViewState.resId = false;
    splitViewState.resModel = null;
}

export function setSplitActive(value) {

    if (session.default_split_view) {
        splitViewState.active = true;

        if (!value) {
            closeSplit();
        }

        return;
    }

    splitViewState.active = value;

    browser.localStorage.setItem(
        ACTIVE_KEY,
        value ? "1" : "0"
    );

    if (!value) {
        closeSplit();
    }
}

export function setSplitGate(value) {
    splitViewState.gate = value;

    browser.localStorage.setItem(
        GATE_KEY,
        value ? "1" : "0"
    );

    if (!value) {
        setSplitActive(false);
    } else if (session.default_split_view) {
        setSplitActive(true);
    }
}

export function toggleSplitDirection() {
    if (!isDirectionToggleEnabled()) {
        return;
    }

    splitViewState.direction =
        splitViewState.direction === "horizontal"
            ? "vertical"
            : "horizontal";

    browser.localStorage.setItem(
        DIRECTION_KEY,
        splitViewState.direction
    );
}

export function notifySplitSaved() {
    splitViewState.syncTick++;
}

export function notifyHostRefreshed() {
    splitViewState.hostRefreshTick++;
}