import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { PrepDisplay } from "@pos_enterprise/app/components/preparation_display/preparation_display";
import { Order } from "@pos_enterprise/app/components/order/order";
import { Orderline } from "@pos_enterprise/app/components/orderline/orderline";
import { _t } from "@web/core/l10n/translation";

const PRIORITY_LABELS = { low: _t("Low"), medium: _t("Medium"), high: _t("High") };
const CHANGE_HIGHLIGHT_MS = 5 * 60 * 1000;

function inPreparation(state) {
    return Boolean(
        state?.stage_id && ["todo", "in_progress"].includes(state.stage_id.stage_type) && state.todo
    );
}

function viewingPreparation(prepDisplay) {
    const id = prepDisplay.selectedStageId;
    if (!id) {
        return true; 
    }
    const stage = prepDisplay.data.models["pos.prep.stage"].get(id);
    return ["todo", "in_progress"].includes(stage?.stage_type);
}

/* main screen */
PrepDisplay.components = { ...PrepDisplay.components, Dropdown, DropdownItem };
patch(PrepDisplay.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useState(this.prepDisplay.kitchen);
    },

    get kitchenRootClass() {
        return this.prepDisplay.kitchenAdvanced ? "o_kitchen_active" : "";
    },
    get kitchenChefLabel() {
        if (this.prepDisplay.kitchenRestricted && !this.kitchen.access?.chef) {
            return _t("No chef profile");
        }
        return this.kitchen.chef ? this.kitchen.chef.name : _t("All chefs");
    },
    get kitchenIsManager() {
        return this.prepDisplay.kitchenIsManager;
    },
    get showStationFilter() {
        return this.prepDisplay.kitchenAdvanced && this.prepDisplay.visibleStations.length > 1;
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
        if (value === "all") {
            this.prepDisplay.logoutChef();
            return;
        }
        this.kitchen.chefFilter = value;
    },
    setPriorityFilter(value) {
        this.kitchen.priorityFilter = value;
    },
});

/* ticket card */
patch(Order.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useState(this.prepDisplay.kitchen);
    },

    get cardColor() {
        const base = super.cardColor;
        if (!this.prepDisplay.kitchenAdvanced || this.order.priority !== "high") {
            return base;
        }
        return "o_pdis_card_color_1 o_kitchen_urgent";
    },
    get kitchenShowPriority() {
        return this.prepDisplay.kitchenAdvanced && this.order.priority !== "medium";
    },
    get kitchenPriorityLabel() {
        return PRIORITY_LABELS[this.order.priority] || "";
    },
    get kitchenIsOverflow() {
        return this.prepDisplay.isOverflowOrder(this.order.pos_order_id?.id);
    },
    get kitchenShowToolbar() {
        return this.prepDisplay.kitchenAdvanced && (this.kitchenIsOverflow || this.kitchenReadiness);
    },
    get kitchenReadiness() {
        if (!this.prepDisplay.kitchenAdvanced) {
            return null;
        }
        const posOrder = this.order.pos_order_id;
        const status = Object.values(posOrder?.kitchen_station_status || {});
        if (status.length < 2) {
            return null; // a single station has nothing to coordinate
        }
        const ready = status.filter((s) => s.total && s.ready === s.total).length;
        const readiness = posOrder.kitchen_readiness;
        if (readiness === "ready" || readiness === "served") {
            return null; // nothing left to coordinate: no "All ready" badge
        }
        return {
            text: _t("%(ready)s of %(total)s stations ready", { ready, total: status.length }),
            cls: readiness === "partial_ready" ? "text-bg-warning" : "text-bg-secondary",
            stations: status,
        };
    },
    get kitchenReprepare() {
        if (!this.prepDisplay.kitchenAdvanced || !viewingPreparation(this.prepDisplay)) {
            return false;
        }
        return this.props.order.states.some((state) => {
            const line = state.prep_line_id;
            return line.last_change_type === "reprep" && line.change_pending && inPreparation(state);
        });
    },
    get kitchenOrderChanged() {
        if (!this.prepDisplay.kitchenAdvanced || !viewingPreparation(this.prepDisplay)) {
            return false;
        }
        return this.props.order.states.some((state) => {
            const line = state.prep_line_id;
            if (line.last_change_type === "reprep") {
                return false;
            }
            return (
                line.change_pending ||
                (line.last_change_type === "qty_increased" &&
                    line.last_change_at &&
                    this.kitchen.now - line.last_change_at.ts < CHANGE_HIGHLIGHT_MS)
            );
        });
    },
});

/* item line */
patch(Orderline.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useState(this.prepDisplay.kitchen);
    },

    get kitchenState() {
        return this.props.orderline.stage_id ? this.props.orderline : null;
    },
    get kitchenChangeText() {
        const line = this.preparation_line;
        if (
            !this.prepDisplay.kitchenAdvanced ||
            !line.change_text ||
            !viewingPreparation(this.prepDisplay)
        ) {
            return null;
        }
        if (line.last_change_type === "reprep") {
            return line.change_pending && inPreparation(this.kitchenState)
                ? { text: line.change_text, cls: "o_kitchen_change_reprep" }
                : null;
        }
        if (line.change_pending) {
            return { text: line.change_text, cls: "o_kitchen_change_pending" };
        }
        const recent =
            line.last_change_at && this.kitchen.now - line.last_change_at.ts < CHANGE_HIGHLIGHT_MS;
        if (recent && line.last_change_type === "qty_increased") {
            return { text: line.change_text, cls: "o_kitchen_change_info" };
        }
        return null;
    },
    get kitchenStationName() {
        if (!this.prepDisplay.kitchenAdvanced || this.prepDisplay.ownStations.length < 2) {
            return "";
        }
        return this.preparation_line.station_id?.name || "";
    },
    get kitchenChef() {
        return this.prepDisplay.kitchenAdvanced ? this.preparation_line.assigned_chef_id || null : null;
    },
    get kitchenChefAuto() {
        return Boolean(this.kitchenChef && this.preparation_line.chef_assignment === "auto");
    },
    get kitchenCanAssign() {
        const state = this.kitchenState;
        return Boolean(
            state && this.prepDisplay.kitchenAdvanced && state.stage_id.stage_type !== "done"
        );
    },
    get kitchenMovedFrom() {
        return this.prepDisplay.kitchenAdvanced ? this.preparation_line.moved_from || "" : "";
    },
    get kitchenCanMove() {
        const state = this.kitchenState;
        return Boolean(
            state &&
                this.prepDisplay.kitchenAdvanced &&
                this.prepDisplay.kitchenIsManager &&
                state.stage_id.stage_type === "todo" &&
                state.todo &&
                this.prepDisplay.moveTargetsFor([this.preparation_line]).length
        );
    },
    get kitchenIsManager() {
        return this.prepDisplay.kitchenIsManager;
    },
    get kitchenCanReprepare() {
        const state = this.kitchenState;
        const line = this.preparation_line;
        return Boolean(
            state &&
                line &&
                this.prepDisplay.kitchenAdvanced &&
                state.stage_id.stage_type === "ready" &&
                line.quantity - (line.cancelled || 0) > 0
        );
    },
    get kitchenMetaVisible() {
        return Boolean(
            this.prepDisplay.kitchenAdvanced &&
                (this.kitchenMovedFrom ||
                    this.kitchenStationName ||
                    this.kitchenCanAssign ||
                    this.kitchenCanReprepare)
        );
    },
    kitchenReprepareClick() {
        this.prepDisplay.openReprepareDialog([this.kitchenState]);
    },
    kitchenAssign() {
        this.prepDisplay.openAssignMenu([this.kitchenState]);
    },
    kitchenMove() {
        this.prepDisplay.openReassignMenu([this.kitchenState]);
    },
    kitchenTake() {
        this.prepDisplay.takeStates([this.kitchenState]);
    },
});