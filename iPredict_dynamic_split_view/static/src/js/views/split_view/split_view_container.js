/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillUnmount,
    useRef,
    useState,
    useSubEnv,
} from "@odoo/owl";

import { View, getDefaultConfig } from "@web/views/view";
import { browser } from "@web/core/browser/browser";
import { SIZES } from "@web/core/ui/ui_service";

import { splitViewState } from "./split_view_state";

const SIZE_KEY = "ipredict_split_view_size_pct";

const DEFAULT_PCT = 50;
const MIN_PCT = 20;
const MAX_PCT = 80;

const WIDE_THRESHOLD_PX = 1100;

export class SplitViewContainer extends Component {
    static template =
        "ipredict_dynamic_split_view.SplitViewContainer";

    static components = {
        View,
    };

    static props = {
        resModel: String,
        resId: {
            type: [Number, Boolean],
            optional: true,
        },
    };

    setup() {
        const host = this.env.config;
        const ui = this.env.services.ui;

        this._realUi = ui;

        this.sizeState = useState({
            value: Math.min(ui.size, SIZES.XL),
        });

        const splitUi = new Proxy(ui, {
            get: (target, prop) => {
                if (prop === "size") {
                    return this.sizeState.value;
                }

                return Reflect.get(target, prop);
            },
        });

        useSubEnv({
            inSplitView: true,

            services: {
                ...this.env.services,
                ui: splitUi,
            },

            config: {
                ...getDefaultConfig(),
                viewType: "form",
                actionId: host.actionId,
                views: host.views,
            },
        });

        this.splitViewState = useState(splitViewState);

        this.dividerRef = useRef("divider");
        this.panelRef = useRef("panel");

        this.currentPct = null;
        this._resizeTimeout = null;

        this._onWindowResize = () => {
            clearTimeout(this._resizeTimeout);

            this._resizeTimeout = setTimeout(
                () => this.recomputeSize(),
                200
            );
        };

        onMounted(() => {
            const saved = parseFloat(
                browser.localStorage.getItem(SIZE_KEY)
            );

            this.applySize(
                saved >= MIN_PCT && saved <= MAX_PCT
                    ? saved
                    : DEFAULT_PCT
            );

            this.recomputeSize();

            browser.addEventListener(
                "resize",
                this._onWindowResize
            );
        });

        onWillUnmount(() => {
            clearTimeout(this._resizeTimeout);

            browser.removeEventListener(
                "resize",
                this._onWindowResize
            );

            this.parentEl?.style.removeProperty(
                "--ipredict-split-left"
            );

            this.parentEl?.style.removeProperty(
                "--ipredict-split-top"
            );

            document.body.classList.remove(
                "o_ipredict_resizing"
            );
        });
    }

    recomputeSize() {
        const panelWidth =
            this.panelRef.el?.getBoundingClientRect().width ?? 0;

        const next =
            panelWidth >= WIDE_THRESHOLD_PX
                ? this._realUi.size
                : Math.min(
                      this._realUi.size,
                      SIZES.XL
                  );

        if (next !== this.sizeState.value) {
            this.sizeState.value = next;
        }
    }

    get parentEl() {
        return this.dividerRef.el?.parentElement;
    }

    applySize(pct) {
        if (splitViewState.direction === "horizontal") {
            this.parentEl?.style.setProperty(
                "--ipredict-split-left",
                `${pct}%`
            );

            this.parentEl?.style.removeProperty(
                "--ipredict-split-top"
            );
        } else {
            this.parentEl?.style.setProperty(
                "--ipredict-split-top",
                `${pct}%`
            );

            this.parentEl?.style.removeProperty(
                "--ipredict-split-left"
            );
        }
    }

    onDividerPointerDown(ev) {
        const divider = this.dividerRef.el;
        const parent = this.parentEl;z

        if (!divider || !parent) {
            return;
        }

        ev.preventDefault();

        divider.setPointerCapture(ev.pointerId);

        document.body.classList.add(
            "o_ipredict_resizing"
        );

        const onMove = (e) => {
            const rect = parent.getBoundingClientRect();

            const pct =
                splitViewState.direction === "horizontal"
                    ? ((e.clientX - rect.left) /
                          rect.width) *
                      100
                    : ((e.clientY - rect.top) /
                          rect.height) *
                      100;

            this.currentPct = Math.min(
                MAX_PCT,
                Math.max(MIN_PCT, pct)
            );

            this.applySize(this.currentPct);
        };

        const onUp = (e) => {
            divider.releasePointerCapture?.(
                e.pointerId
            );

            divider.removeEventListener(
                "pointermove",
                onMove
            );

            divider.removeEventListener(
                "pointerup",
                onUp
            );

            document.body.classList.remove(
                "o_ipredict_resizing"
            );

            if (this.currentPct) {
                browser.localStorage.setItem(
                    SIZE_KEY,
                    String(
                        Math.round(
                            this.currentPct
                        )
                    )
                );
            }

            this.recomputeSize();
        };

        divider.addEventListener(
            "pointermove",
            onMove
        );

        divider.addEventListener(
            "pointerup",
            onUp
        );
    }

    onDividerDblClick() {
        this.currentPct = DEFAULT_PCT;

        this.applySize(DEFAULT_PCT);

        browser.localStorage.setItem(
            SIZE_KEY,
            String(DEFAULT_PCT)
        );

        this.recomputeSize();
    }
}