import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

/**
 * _mergedSourceTables — Merge tracking
 * Key   → sourceTable.id
 * Value → destOrder uuid/id
 */
const _mergedSourceTables = new Map();

patch(PosStore.prototype, {
    async mergeOrders(sourceOrder, destOrder) {
        const sourceTable = sourceOrder?.table_id;

        // Backend field check — check if either source or destination is auto-assigned
        const isAutoAssigned =
            destOrder?.is_guest_queue_auto_assigned === true ||
            sourceOrder?.is_guest_queue_auto_assigned === true;

        const result = await super.mergeOrders(...arguments);

        if (isAutoAssigned === true && sourceTable) {
            const destOrderId = destOrder?.uuid || destOrder?.id;
            if (destOrderId) {
                _mergedSourceTables.set(sourceTable.id, destOrderId);
            }

            const existingOrders = this.getTableOrders(sourceTable.id);
            if (!existingOrders.length) {
                const newOrder = this.addNewOrder({ table_id: sourceTable });
                newOrder.setBooked(true);
                newOrder.is_guest_queue_auto_assigned = true;
                this.addPendingOrder([newOrder.id]);
                await this.syncAllOrders({ orders: [newOrder] });
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
                const sessionId = this.session?.id;

                if (sessionId) {
                    const guest = await this.data.call(
                        "pos.guest.queue",
                        "find_notified_guest_by_partner",
                        [partner.id, sessionId]
                    );

                    if (guest?.id) {
                        await this.data.call(
                            "pos.guest.queue",
                            "mark_guest_seated",
                            [guest.id]
                        );
                    }
                }
            }
        } catch (e) {
        }

        return result;
    },
});

export { _mergedSourceTables };