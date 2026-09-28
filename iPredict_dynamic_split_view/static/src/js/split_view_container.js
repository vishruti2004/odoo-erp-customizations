/** @odoo-module **/
import { Component, onMounted, onWillUnmount, useRef, useSubEnv } from "@odoo/owl";
import { View, getDefaultConfig } from "@web/views/view";
import { browser } from "@web/core/browser/browser";
import { SIZES } from "@web/core/ui/ui_service";

const WIDTH_KEY = "ipredict_split_view_left_pct";
const DEFAULT_PCT = 50;
const MIN_PCT = 20;
const MAX_PCT = 80;

export class SplitViewContainer extends Component {
    static template = "ipredict_dynamic_split_view.SplitViewContainer";
    static components = { View };
    static props = { resModel: String, resId: Number };

    setup() {
        const host = this.env.config;
        const ui = this.env.services.ui;
        const splitUi = new Proxy(ui, {
            get(target, prop) {
                if (prop === "size") {
                    return Math.min(target.size, SIZES.XL);
                }
                return Reflect.get(target, prop);
            },
        });

        useSubEnv({
            inSplitView: true,
            services: { ...this.env.services, ui: splitUi },
            config: {
                ...getDefaultConfig(),
                viewType: "form",
                actionId: host.actionId,
                views: host.views,
            },
        });

        this.dividerRef = useRef("divider");
        this.currentPct = null;

        onMounted(() => {
            const saved = parseFloat(browser.localStorage.getItem(WIDTH_KEY));
            this.applyWidth(saved >= MIN_PCT && saved <= MAX_PCT ? saved : DEFAULT_PCT);
        });
        onWillUnmount(() => {
            this.parentEl?.style.removeProperty("--ipredict-split-left");
            document.body.classList.remove("o_ipredict_resizing");
        });
    }

    get parentEl() {
        return this.dividerRef.el?.parentElement;
    }

    applyWidth(pct) {
        this.parentEl?.style.setProperty("--ipredict-split-left", `${pct}%`);
    }

    onDividerPointerDown(ev) {
        const divider = this.dividerRef.el;
        const parent = this.parentEl;
        if (!divider || !parent) {
            return;
        }
        ev.preventDefault();
        divider.setPointerCapture(ev.pointerId);
        document.body.classList.add("o_ipredict_resizing");

        const onMove = (e) => {
            const rect = parent.getBoundingClientRect();
            const pct = ((e.clientX - rect.left) / rect.width) * 100;
            this.currentPct = Math.min(MAX_PCT, Math.max(MIN_PCT, pct));
            this.applyWidth(this.currentPct);
        };
        const onUp = (e) => {
            divider.releasePointerCapture?.(e.pointerId);
            divider.removeEventListener("pointermove", onMove);
            divider.removeEventListener("pointerup", onUp);
            document.body.classList.remove("o_ipredict_resizing");
            if (this.currentPct) {
                browser.localStorage.setItem(WIDTH_KEY, String(Math.round(this.currentPct)));
            }
        };
        divider.addEventListener("pointermove", onMove);
        divider.addEventListener("pointerup", onUp);
    }

    onDividerDblClick() {
        this.currentPct = DEFAULT_PCT;
        this.applyWidth(DEFAULT_PCT);
        browser.localStorage.setItem(WIDTH_KEY, String(DEFAULT_PCT));
    }
}