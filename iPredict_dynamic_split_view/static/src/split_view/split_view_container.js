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
import { MEDIAS_BREAKPOINTS, SIZES } from "@web/core/ui/ui_service";
import { splitViewState } from "./split_view_state";

function contentWidth(el) {
    let left = null;
    let right = null;
    const add = (rect) => {
        if (rect.width) {
            left = Math.min(left ?? rect.left, rect.left);
            right = Math.max(right ?? rect.right, rect.right);
        }
    };
    const range = document.createRange();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
        if (walker.currentNode.textContent.trim()) {
            range.selectNodeContents(walker.currentNode);
            [...range.getClientRects()].forEach(add);
        }
    }
    el.querySelectorAll("i, img, svg").forEach((icon) => add(icon.getBoundingClientRect()));
    return right === null ? 0 : right - left;
}

function neededRight(el) {
    const style = getComputedStyle(el);
    return (
        el.getBoundingClientRect().left +
        parseFloat(style.paddingLeft) +
        contentWidth(el) +
        parseFloat(style.paddingRight)
    );
}

export class SplitViewContainer extends Component {
    static template = "iPredict_dynamic_split_view.SplitViewContainer";

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

        this._panelObserver = new ResizeObserver(() => this.recomputeSize());
        this._parentObserver = new ResizeObserver(() => this.applySize(this.savedPct));

        useEffect(
            () => this.applySize(this.savedPct),
            () => [this.direction]
        );

        onMounted(() => {
            this.recomputeSize();
            if (this.panelRef.el) {
                this._panelObserver.observe(this.panelRef.el);
            }
            if (this.parentEl) {
                this._parentObserver.observe(this.parentEl);
            }
        });

        onWillUnmount(() => {
            this._panelObserver.disconnect();
            this._parentObserver.disconnect();
            this.parentEl?.style.removeProperty("--ipredict-split-left");
            this.parentEl?.style.removeProperty("--ipredict-split-top");
            document.body.classList.remove("o_ipredict_resizing");
        });
    }
    get direction() {
        return this.uiState.isSmall ? "vertical" : this.splitViewState.direction;
    }

    get isHorizontal() {
        return this.direction === "horizontal";
    }

    get parentEl() {
        return this.dividerRef.el?.parentElement;
    }

    get storageKey() {
        return `ipredict_split_view_size_pct_${this.direction}`;
    }

    getMinSizes() {
        const parentRect = this.parentEl?.getBoundingClientRect();
        const renderer = this.parentEl?.querySelector(":scope > .o_renderer");
        const panel = this.panelRef.el;
        if (!parentRect) {
            return { list: 0, form: 0 };
        }
        if (this.isHorizontal) {
            let listEnd = renderer?.getBoundingClientRect().left ?? parentRect.left;
            const firstColumn = renderer?.querySelector("thead th:not(.o_list_record_selector)");
            if (firstColumn) {
                const firstCell = renderer.querySelector(
                    `tbody .o_data_row > :nth-child(${firstColumn.cellIndex + 1})`
                );
                listEnd = Math.max(neededRight(firstColumn), firstCell ? neededRight(firstCell) : 0);
            } else if (renderer?.classList.contains("o_kanban_renderer")) {
                const cardWidth = parseFloat(
                    getComputedStyle(renderer).getPropertyValue("--KanbanRecord-width")
                );
                listEnd += Number.isFinite(cardWidth) ? cardWidth : 0;
            }
            const breadcrumbs = panel?.querySelector(".o_control_panel_breadcrumbs");
            const panelLeft = panel?.getBoundingClientRect().left ?? 0;
            return {
                list: Math.max(listEnd - parentRect.left, 0),
                form: breadcrumbs ? Math.max(neededRight(breadcrumbs) - panelLeft, 0) : 0,
            };
        }
        const height = (el) => el?.getBoundingClientRect().height || 0;
        const listTop = renderer?.getBoundingClientRect().top ?? parentRect.top;
        return {
            list:
                Math.max(listTop - parentRect.top, 0) +
                height(renderer?.querySelector("thead")) +
                height(renderer?.querySelector(".o_data_row, .o_kanban_record")),
            form:
                height(panel?.querySelector(".o_control_panel")) +
                height(panel?.querySelector(".o_form_statusbar")),
        };
    }

    getPctRange() {
        const rect = this.parentEl?.getBoundingClientRect();
        const total = (this.isHorizontal ? rect?.width : rect?.height) || 0;
        if (!total) {
            return null;
        }
        const divider = this.dividerRef.el?.getBoundingClientRect();
        const dividerSize = (this.isHorizontal ? divider?.width : divider?.height) || 0;
        const { list, form } = this.getMinSizes();
        const equal = ((total + dividerSize) / (2 * total)) * 100;
        const min = (list / total) * 100;
        const max = ((total - form - dividerSize) / total) * 100;
        if (min >= max) {
            const share = (list / (list + form)) * 100;
            return { min: share, max: share, equal: share };
        }
        return { min, max, equal };
    }

    clampPct(pct) {
        const range = this.getPctRange();
        if (!range) {
            return pct;
        }
        const value = Number.isFinite(pct) ? pct : range.equal;
        return Math.min(range.max, Math.max(range.min, value));
    }

    get savedPct() {
        return parseFloat(browser.localStorage.getItem(this.storageKey));
    }
    computePanelSize(width) {
        if (!width) {
            return Math.min(this._realUi.size, SIZES.XL);
        }
        const index = MEDIAS_BREAKPOINTS.findIndex(
            ({ minWidth = 0, maxWidth = Infinity }) => width >= minWidth && width <= maxWidth
        );
        return index === -1 ? SIZES.XXL : index;
    }

    recomputeSize() {
        const panelWidth = this.panelRef.el?.getBoundingClientRect().width ?? 0;
        const next = Math.min(this._realUi.size, this.computePanelSize(panelWidth));
        if (next !== this.sizeState.value) {
            this.sizeState.value = next;
            this._realUi.bus.trigger("resize");
            browser.dispatchEvent(new Event("resize"));
        }
    }

    applySize(pct) {
        const value = this.clampPct(pct);
        if (!Number.isFinite(value)) {
            return;
        }
        if (this.isHorizontal) {
            this.parentEl?.style.setProperty("--ipredict-split-left", `${value}%`);
            this.parentEl?.style.removeProperty("--ipredict-split-top");
        } else {
            this.parentEl?.style.setProperty("--ipredict-split-top", `${value}%`);
            this.parentEl?.style.removeProperty("--ipredict-split-left");
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
        document.body.classList.add("o_ipredict_resizing");

        const onMove = (e) => {
            const rect = parent.getBoundingClientRect();
            const pct = this.isHorizontal
                ? ((e.clientX - rect.left) / rect.width) * 100
                : ((e.clientY - rect.top) / rect.height) * 100;
            this.currentPct = this.clampPct(pct);
            this.applySize(this.currentPct);
        };

        const onUp = (e) => {
            divider.releasePointerCapture?.(e.pointerId);
            divider.removeEventListener("pointermove", onMove);
            divider.removeEventListener("pointerup", onUp);
            document.body.classList.remove("o_ipredict_resizing");
            if (Number.isFinite(this.currentPct)) {
                browser.localStorage.setItem(this.storageKey, String(this.currentPct));
            }
        };

        divider.addEventListener("pointermove", onMove);
        divider.addEventListener("pointerup", onUp);
    }

    onDividerDblClick() {
        browser.localStorage.removeItem(this.storageKey);
        this.currentPct = null;
        this.applySize(NaN);
    }
}