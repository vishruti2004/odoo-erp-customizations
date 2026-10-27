import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { Order } from "@pos_enterprise/app/components/order/order";
import { inPreparation, viewingPreparation } from "@pos_kitchen_screen/app/utils/kitchen_utils";

const PRIORITY_LABELS = { low: _t("Low"), medium: _t("Medium"), high: _t("High") };

patch(Order.prototype, {
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
            return null;
        }
        const ready = status.filter((station) => station.total && station.ready === station.total).length;
        const readiness = posOrder.kitchen_readiness;
        if (readiness === "ready" || readiness === "served") {
            return null;
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
            return line.last_change_type !== "reprep" && line.change_pending;
        });
    },
});
