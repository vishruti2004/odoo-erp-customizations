/** @odoo-module **/

import { registry } from "@web/core/registry";

// Checks whether the current element is a text-editable field.
function isTextEditable(el) {
    if (!el || el.nodeType !== 1) {
        return false;
    }

    if (el.isContentEditable || el.tagName === "TEXTAREA") {
        return true;
    }

    return el.tagName === "INPUT" && el.type !== "checkbox";
}

// Checks whether the user has selected text on the page.
function hasTextSelection() {
    const selection = window.getSelection?.();

    return Boolean(
        selection &&
        !selection.isCollapsed &&
        selection.toString().trim()
    );
}

export const o2mKeyboardService = {
    dependencies: ["o2m_copy_paste"],

    start(_env, { o2m_copy_paste: clipboard }) {
        window.addEventListener(
            "pointerdown",
            (ev) => clipboard.setActiveFromTarget(ev.target),
            true
        );
        window.addEventListener(
            "focusin",
            (ev) => clipboard.setActiveFromTarget(ev.target),
            true
        );
        window.addEventListener("keydown", async (ev) => {
            if (
                ev.defaultPrevented ||
                !(ev.ctrlKey || ev.metaKey) ||
                ev.altKey ||
                ev.shiftKey
            ) {
                return;
            }

            const isCopy = ev.code === "KeyC";
            const isPaste = ev.code === "KeyV";

            if (!isCopy && !isPaste) {
                return;
            }

            if (isTextEditable(ev.target)) {
                return;
            }

            if (isCopy) {
                if (hasTextSelection()) {
                    return;
                }

                const source = clipboard.pickSource();

                if (source) {
                    ev.preventDefault();
                    clipboard.copy(source);
                }

                return;
            }

            if (!clipboard.hasRenderers()) {
                return;
            }

            const data = clipboard.readClipboard();

            if (!data?.lines?.length) {
                return;
            }

            const { renderer, reason } = clipboard.pickTarget(data);

            ev.preventDefault();

            if (!renderer) {
                clipboard.notifyNoTarget(reason);
                return;
            }

            await clipboard.paste(renderer, data);
        });
    },
};

registry.category("services").add("o2m_keyboard", o2mKeyboardService);