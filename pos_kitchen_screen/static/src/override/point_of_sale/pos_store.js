import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async setKitchenPriority(order, priority) {
        if (!order || !["high", "medium", "low"].includes(priority)) {
            return;
        }
        order.kitchen_priority = priority;
        if (typeof order.id === "number") {
            await this.data.call("pos.order", "set_kitchen_priority", [[order.id], priority]);
        }
    },
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
        const order = this.models["pos.order"].find((order) => order.id === orderId);
        if (order?.uiState) {
            order.uiState.kitchen_locked = Boolean(locked);
        }
    },
    async kitchenRefreshLocks(orders) {
        if (!this.config?.kitchen_advanced) {
            return;
        }
        const list = (orders || this.models["pos.order"].filter((order) => !order.finalized)).filter(
            (order) => typeof order.id === "number" && order.uiState
        );
        if (!list.length) {
            return;
        }
        try {
            const locked = await this.data.call("pos.order", "get_kitchen_locked_ids", [
                list.map((order) => order.id),
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
