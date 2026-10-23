import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";

patch(PosOrder.prototype, {
    get kitchenLocked() {
        return Boolean(this.uiState?.kitchen_locked);
    },
});

patch(PosStore.prototype, {
    async afterProcessServerData() {
        const result = await super.afterProcessServerData(...arguments);
        if (this.config?.kitchen_advanced) {
            this.data.connectWebSocket("KITCHEN_ORDER_LOCK", (data) =>
                this.kitchenSetLocked(data.order_id, data.locked)
            );
            this.kitchenRefreshLocks();
        }
        return result;
    },
    setOrder(order) {
        super.setOrder(...arguments);
        if (order) {
            this.kitchenRefreshLocks([order]);
        }
    },
    kitchenSetLocked(orderId, locked) {
        const order = this.models["pos.order"].find((o) => o.id === orderId);
        if (order?.uiState) {
            order.uiState.kitchen_locked = Boolean(locked);
        }
    },
    async kitchenRefreshLocks(orders) {
        if (!this.config?.kitchen_advanced) {
            return;
        }
        const list = (orders || this.models["pos.order"].filter((o) => !o.finalized)).filter(
            (o) => typeof o.id === "number" && o.uiState
        );
        if (!list.length) {
            return;
        }
        try {
            const locked = await this.data.call("pos.order", "get_kitchen_locked_ids", [
                list.map((o) => o.id),
            ]);
            for (const order of list) {
                order.uiState.kitchen_locked = locked.includes(order.id);
            }
        } catch {
        }
    },
    async addLineToCurrentOrder() {
        if (this.getOrder()?.kitchenLocked) {
            return;
        }
        return super.addLineToCurrentOrder(...arguments);
    },
    async submitOrder() {
        if (this.getOrder()?.kitchenLocked) {
            return;
        }
        return super.submitOrder(...arguments);
    },
    async sendOrderInPreparationUpdateLastChange(order) {
        if (order?.kitchenLocked) {
            return;
        }
        return super.sendOrderInPreparationUpdateLastChange(...arguments);
    },
});

patch(OrderSummary.prototype, {
    async updateSelectedOrderline() {
        if (this.currentOrder?.kitchenLocked) {
            this.numberBuffer.reset();
            return;
        }
        return super.updateSelectedOrderline(...arguments);
    },
});

patch(ProductScreen.prototype, {
    onNumpadClick() {
        if (this.currentOrder?.kitchenLocked) {
            return;
        }
        return super.onNumpadClick(...arguments);
    },
    displayAllControlPopup() {
        if (this.currentOrder?.kitchenLocked) {
            this.notification.add(
                _t("This order is ready in the kitchen and can no longer be changed."),
                { type: "warning" }
            );
            return;
        }
        return super.displayAllControlPopup(...arguments);
    },
});
