/** @odoo-module **/

import {
    Component,
    onMounted,
    onWillUnmount,
    useEffect,
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

// Same breakpoints as Odoo (MEDIAS_BREAKPOINTS), applied to the split panel width
const PANEL_BREAKPOINTS = [
    [576, SIZES.XS],
    [768, SIZES.SM],
    [992, SIZES.MD],
    [1200, SIZES.LG],
    [1400, SIZES.XL],
];

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
        // Reactive read of ui.isSmall: the direction follows mobile/desktop changes
        this.uiState = useState(ui);

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

        // The form follows the width of the split panel, not the window
        this._resizeObserver = new ResizeObserver(() => this.recomputeSize());

        // Apply the saved size on mount and whenever the direction changes
        useEffect(
            () => {
                const saved = parseFloat(
                    browser.localStorage.getItem(SIZE_KEY)
                );

                this.applySize(
                    saved >= MIN_PCT && saved <= MAX_PCT
                        ? saved
                        : DEFAULT_PCT
                );
            },
            () => [this.direction]
        );

        onMounted(() => {
            this.recomputeSize();

            if (this.panelRef.el) {
                this._resizeObserver.observe(this.panelRef.el);
            }
        });

        onWillUnmount(() => {
            this._resizeObserver.disconnect();

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

    /**
     * Mobile: always vertical. Desktop: the direction chosen by the user.
     */
    get direction() {
        return this.uiState.isSmall ? "vertical" : this.splitViewState.direction;
    }

    computePanelSize(width) {
        if (!width) {
            return Math.min(this._realUi.size, SIZES.XL);
        }
        const match = PANEL_BREAKPOINTS.find(([maxWidth]) => width < maxWidth);
        return match ? match[1] : SIZES.XXL;
    }

    recomputeSize() {
        const panelWidth =
            this.panelRef.el?.getBoundingClientRect().width ?? 0;

        const next = Math.min(
            this._realUi.size,
            this.computePanelSize(panelWidth)
        );

        if (next !== this.sizeState.value) {
            this.sizeState.value = next;
            // Same signals as Odoo's ui service: FormController listens to the
            // ui bus, FormRenderer (web + mail) listens to the window resize.
            this._realUi.bus.trigger("resize");
            browser.dispatchEvent(new Event("resize"));
        }
    }

    get parentEl() {
        return this.dividerRef.el?.parentElement;
    }

    applySize(pct) {
        if (this.direction === "horizontal") {
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
        const parent = this.parentEl;

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
                this.direction === "horizontal"
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
    }
}
