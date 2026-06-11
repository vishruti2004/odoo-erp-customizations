import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

const _autoAssignMergedTables = new Map();

patch(PosStore.prototype, {
    async mergeOrders(sourceOrder, destOrder) {
        const sourceTable = sourceOrder.table_id;

        // before merge check auto assign or not
        const isAutoAssigned = destOrder?.uiState?._guestQueueAutoAssigned ||
            sourceOrder?.uiState?._guestQueueAutoAssigned;

        const result = await super.mergeOrders(...arguments);

        // auto flow -- waiter flow auto default
        if (isAutoAssigned && sourceTable) {
            const existingOrders = this.getTableOrders(sourceTable.id);
            if (!existingOrders.length) {
                const newOrder = this.addNewOrder({ table_id: sourceTable });
                newOrder.setBooked(true);
                newOrder.uiState._guestQueueAutoAssigned = true;
                this.addPendingOrder([newOrder.id]);
                await this.syncAllOrders({ orders: [newOrder] });
            }

            const destId = result?.id || result?.uuid;
            if (destId) {
                if (!_autoAssignMergedTables.has(destId)) {
                    _autoAssignMergedTables.set(destId, []);
                }
                _autoAssignMergedTables.get(destId).push(sourceTable.id);
            }
        }

        return result;
    },

    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        const result = await super.addLineToCurrentOrder(...arguments);
        try {
            const order = this.getOrder();
            const partner = order?.getPartner();
            if (partner) {
                const guest = await this.data.call(
                    "pos.guest.queue",
                    "find_notified_guest_by_partner",
                    [partner.id]
                );
                if (guest && guest.id) {
                    await this.data.call(
                        "pos.guest.queue",
                        "mark_guest_seated",
                        [guest.id]
                    );
                    console.log(`Guest ${guest.guest_name} marked as seated`);
                }
            }
        } catch (e) {
            console.error("Error marking guest seated:", e);
        }
        return result;
    },
});