/** @odoo-module **/

import { registry } from "@web/core/registry";

const NON_TEXT_INPUTS = ["checkbox", "radio", "button", "submit", "reset", "image", "range", "color", "file"];

function isTextEditable(el) {
    if (el?.nodeType !== 1) {
        return false;
    }
    if (el.isContentEditable || el.tagName === "TEXTAREA") {
        return true;
    }
    return el.tagName === "INPUT" && !NON_TEXT_INPUTS.includes(el.type);
}

function hasTextSelection() {
    return Boolean(window.getSelection?.().toString().trim());
}

export const o2mKeyboardService = {
    dependencies: ["o2m_copy_paste"],

    start(_env, { o2m_copy_paste: clipboard }) {
        let pasting = false;

        for (const eventName of ["pointerdown", "focusin"]) {
            window.addEventListener(eventName, (ev) => clipboard.setActiveFromTarget(ev.target), true);
        }

        async function onCopy(ev) {
            const source = !hasTextSelection() && clipboard.pickSource();
            if (source) {
                ev.preventDefault();
                await clipboard.copy(source);
            }
        }

        async function onPaste(ev) {
            const data = clipboard.readClipboard();
            if (pasting || !data?.lines?.length || !clipboard.hasRenderers()) {
                return;
            }
            ev.preventDefault();
            const { renderer, reason } = clipboard.pickTarget(data);
            if (!renderer) {
                clipboard.notifyNoTarget(reason);
                return;
            }
            pasting = true;
            try {
                await clipboard.paste(renderer, data);
            } finally {
                pasting = false;
            }
        }

        window.addEventListener("keydown", (ev) => {
            if (
                !clipboard.isEnabled() ||
                ev.defaultPrevented ||
                ev.repeat ||
                !(ev.ctrlKey || ev.metaKey) ||
                ev.altKey ||
                ev.shiftKey ||
                isTextEditable(ev.target)
            ) {
                return;
            }
            if (ev.code === "KeyC") {
                onCopy(ev);
            } else if (ev.code === "KeyV") {
                onPaste(ev);
            }
        });
    },
};

registry.category("services").add("o2m_keyboard", o2mKeyboardService);