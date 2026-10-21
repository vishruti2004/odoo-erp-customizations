import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched, onWillUnmount, useState } from "@odoo/owl";
import { PrepDisplay } from "@pos_enterprise/app/components/preparation_display/preparation_display";
import { Order } from "@pos_enterprise/app/components/order/order";
import { Orderline } from "@pos_enterprise/app/components/orderline/orderline";
import { _t } from "@web/core/l10n/translation";

const PRIORITY_LABELS = { low: _t("Low"), medium: _t("Medium"), high: _t("High") };
const READINESS_LABELS = {
    in_progress: _t("In progress"),
    partial_ready: _t("Partially ready"),
    ready: _t("All ready"),
    served: _t("Served"),
};

/*  main screen */
patch(PrepDisplay.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useState(this.prepDisplay.kitchen);
        const pd = this.prepDisplay;
        onMounted(() => {
            if (!pd.kitchenAdvanced) {
                return;
            }
            let saved = NaN;
            try {
                saved = parseFloat(localStorage.getItem(`pdis-zoom-${pd.id}`));
            } catch {
            }
            this.state.zoom = saved || pd.kitchenDisplay.default_zoom || 1;
        });
        onPatched(() => {
            if (pd.kitchenAdvanced) {
                try {
                    localStorage.setItem(`pdis-zoom-${pd.id}`, this.state.zoom);
                } catch {
                }
            }
        });
        this._kitchenKeydown = (ev) => this.onKitchenKeydown(ev);
        onMounted(() => window.addEventListener("keydown", this._kitchenKeydown));
        onWillUnmount(() => window.removeEventListener("keydown", this._kitchenKeydown));
    },

    get kitchenRootClass() {
        const pd = this.prepDisplay;
        if (!pd.kitchenAdvanced) {
            return "";
        }
        const d = pd.kitchenDisplay;
        const cls = [
            "o_kitchen_active",
            `o_pdis_density_${d.ticket_density || "normal"}`,
            `o_kitchen_layout_${d.layout_mode || "grid"}`,
        ];
        if (d.card_columns > 0) {
            cls.push("o_kitchen_fixed_columns");
        }
        return cls.join(" ");
    },
    get kitchenRootStyle() {
        const pd = this.prepDisplay;
        if (!pd.kitchenAdvanced) {
            return "";
        }
        const d = pd.kitchenDisplay;
        const stages = pd.data.models["pos.prep.stage"].getAll().length;
        return `--kitchen-cols: ${d.card_columns || 1}; --kitchen-lanes: ${stages};`;
    },
    get kitchenChefLabel() {
        return this.kitchen.chef ? this.kitchen.chef.name : _t("Chef");
    },
    get showStationFilter() {
        return (
            this.prepDisplay.kitchenOption("show_station") &&
            this.prepDisplay.ownStations.length > 1
        );
    },
    toggleStationFilter(stationId) {
        const list = this.kitchen.stationFilter;
        const idx = list.indexOf(stationId);
        if (idx >= 0) {
            list.splice(idx, 1);
        } else {
            list.push(stationId);
        }
    },
    setChefFilter(value) {
        this.kitchen.chefFilter = value;
    },
    toggleSidebar() {
        this.toggleCategoryFilter();
        this.showSidebar = !this.showSidebar;
    },
    onKitchenKeydown(ev) {
        const pd = this.prepDisplay;
        if (!pd.kitchenOption("enable_shortcuts")) {
            return;
        }
        if (ev.ctrlKey || ev.metaKey || ev.altKey) {
            return;
        }
        const tag = ev.target?.tagName;
        if (
            ["INPUT", "TEXTAREA", "SELECT"].includes(tag) ||
            document.querySelector(".modal.show, .o_dialog")
        ) {
            return;
        }
        switch (ev.key.toLowerCase()) {
            case "n":
                pd.moveFocus(1);
                break;
            case "p":
                pd.moveFocus(-1);
                break;
            case "b":
                pd.bumpFocused();
                break;
            case "r":
                if (this.selectedStage && !this.isHistoryEmpty()) {
                    this.recallLastChange();
                }
                break;
            case "f":
                this.toggleSidebar();
                break;
            default:
                return;
        }
        ev.preventDefault();
    },
});

/*  ticket card */
patch(Order.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useState(this.prepDisplay.kitchen);
    },

    get cardColor() {
        const base = super.cardColor;
        const pd = this.prepDisplay;
        if (!pd.kitchenAdvanced) {
            return base;
        }
        let color = base;
        const extra = [];
        if (pd.kitchenOption("show_priority")) {
            if (this.order.priority === "high") {
                color = "o_pdis_card_color_1";
                extra.push("o_kitchen_urgent");
            }
        }
        if (this.kitchen.focusedStateId && this.props.order.states[0]?.id === this.kitchen.focusedStateId) {
            extra.push("o_kitchen_focused");
        }
        return [color, ...extra].join(" ");
    },

    get kitchenLaneStyle() {
        const pd = this.prepDisplay;
        if (pd.kitchenDisplay?.layout_mode !== "lanes" || pd.selectedStageId !== 0 || !pd.kitchenAdvanced) {
            return "";
        }
        const stages = pd.data.models["pos.prep.stage"].getAll();
        const idx = stages.findIndex((s) => s.id === this.props.order.stage.id);
        return `grid-column: ${idx + 1};`;
    },
    get kitchenShowPriority() {
        return (
            this.prepDisplay.kitchenOption("show_priority") && this.order.priority !== "medium"
        );
    },
    get kitchenPriorityLabel() {
        return PRIORITY_LABELS[this.order.priority] || "";
    },
    get kitchenIsOverflow() {
        return this.prepDisplay.isOverflowOrder(this.order.pos_order_id?.id);
    },
    get kitchenShowToolbar() {
        const pd = this.prepDisplay;
        return (
            pd.kitchenAdvanced &&
            (this.kitchenIsOverflow ||
                pd.kitchenOption("show_chef") ||
                this.kitchenReadiness)
        );
    },
    get kitchenReadiness() {
        const pd = this.prepDisplay;
        if (!pd.kitchenOption("show_readiness")) {
            return null;
        }
        const posOrder = this.order.pos_order_id;
        const status = Object.values(posOrder?.kitchen_station_status || {});
        if (status.length < 2) {
            return null; // single station: nothing to coordinate
        }
        const ready = status.filter((s) => s.total && s.ready === s.total).length;
        const readiness = posOrder.kitchen_readiness;
        return {
            text:
                readiness === "ready" || readiness === "served"
                    ? READINESS_LABELS[readiness]
                    : _t("%(ready)s of %(total)s stations ready", { ready, total: status.length }),
            cls:
                readiness === "ready" || readiness === "served"
                    ? "text-bg-success"
                    : readiness === "partial_ready"
                        ? "text-bg-warning"
                        : "text-bg-secondary",
            stations: status,
        };
    },
    get kitchenChefNames() {
        const names = new Set();
        for (const state of this.props.order.states) {
            const chef = state.prep_line_id.assigned_chef_id;
            if (chef) {
                names.add(chef.name);
            }
        }
        return [...names].join(", ");
    },
    get kitchenUnassignedCount() {
        return this.props.order.states.filter((s) => !s.prep_line_id.assigned_chef_id).length;
    },
    kitchenOpenAssign() {
        this.prepDisplay.openAssignMenu(this.props.order.states);
    },
    kitchenTake() {
        this.prepDisplay.takeStates(this.props.order.states.filter((s) => !s.prep_line_id.assigned_chef_id));
    },
});

/*  item line */
patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useState(this.prepDisplay.kitchen);
    },

    get kitchenState() {
        return this.props.orderline.stage_id ? this.props.orderline : null;
    },
    get kitchenChangeBadge() {
        const pd = this.prepDisplay;
        if (!pd.kitchenAdvanced) {
            return null;
        }
        const line = this.preparation_line;
        const type = line.last_change_type;
        if (!type || type === "none" || !line.last_change_at) {
            return null;
        }
        const minutes = pd.kitchenDisplay.change_highlight_minutes;
        if (minutes > 0 && this.kitchen.now - line.last_change_at.ts > minutes * 60000) {
            return null;
        }
        const map = {
            new_item: [_t("NEW"), "text-bg-success"],
            qty_increased: [`+${line.quantity}`, "text-bg-info"],
            qty_decreased: [`-${line.cancelled}`, "text-bg-warning"],
            cancelled: [_t("CANCELLED"), "text-bg-danger"],
            reprep: [_t("RE-PREP"), "text-bg-danger"],
            note_changed: [_t("NOTE"), "text-bg-primary"],
        };
        const entry = map[type];
        return entry ? { label: entry[0], cls: entry[1] } : null;
    },
    get kitchenStationName() {
        if (!this.prepDisplay.kitchenOption("show_station")) {
            return "";
        }
        return this.preparation_line.station_id?.name || "";
    },
    get kitchenChef() {
        if (!this.prepDisplay.kitchenOption("show_chef")) {
            return null;
        }
        return this.preparation_line.assigned_chef_id || null;
    },
    get kitchenMovedFrom() {
        return this.prepDisplay.kitchenAdvanced ? this.preparation_line.moved_from || "" : "";
    },
    get kitchenReprepCount() {
        return this.prepDisplay.kitchenAdvanced ? this.preparation_line.reprep_count || 0 : 0;
    },
    get kitchenMetaVisible() {
        return (
            this.prepDisplay.kitchenAdvanced &&
            (this.kitchenChangeBadge ||
                this.kitchenMovedFrom ||
                this.kitchenStationName ||
                this.kitchenChef ||
                this.kitchenReprepCount ||
                this.kitchenCanTake ||
                this.kitchenCanMove ||
                this.kitchenCanReprep)
        );
    },
    get kitchenCanTake() {
        const state = this.kitchenState;
        return Boolean(
            state &&
            this.prepDisplay.kitchenOption("show_chef") &&
            !this.preparation_line.assigned_chef_id &&
            state.stage_id.stage_type === "todo" &&
            state.todo
        );
    },
    get kitchenCanMove() {
        const state = this.kitchenState;
        return Boolean(
            state &&
            this.prepDisplay.kitchenOption("show_workload") &&
            state.stage_id.stage_type === "todo" &&
            state.todo &&
            this.prepDisplay.reassignTargets.length
        );
    },
    get kitchenCanReprep() {
        const state = this.kitchenState;
        return Boolean(
            state &&
            this.prepDisplay.kitchenAdvanced &&
            ["ready", "done"].includes(state.stage_id.stage_type)
        );
    },
    kitchenTake() {
        this.prepDisplay.takeStates([this.kitchenState]);
    },
    kitchenAssign() {
        this.prepDisplay.openAssignMenu([this.kitchenState]);
    },
    kitchenMove() {
        this.prepDisplay.openReassignMenu([this.kitchenState]);
    },
    kitchenReprep() {
        this.prepDisplay.openRepreparePrompt([this.kitchenState]);
    },
});
