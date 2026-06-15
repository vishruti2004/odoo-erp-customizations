import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

const _mergedSourceTables = new Map();

patch(PosStore.prototype, {
    /**
     * Handle table merge operation
     * - Auto-assigned orders: Keep source table occupied with placeholder order
     * - Manual orders: Odoo default behavior (source table becomes empty)
     */
    async mergeOrders(sourceOrder, destOrder) {
        const sourceTable = sourceOrder?.table_id;

        // Check if this is an auto-assigned order
        let isAutoAssigned =
            destOrder?.uiState?._guestQueueAutoAssigned ||
            sourceOrder?.uiState?._guestQueueAutoAssigned;

        if (!isAutoAssigned) {
            try {
                const partnerId = destOrder?.partner_id?.id || sourceOrder?.partner_id?.id;
                if (partnerId) {
                    const guest = await this.data.call(
                        "pos.guest.queue",
                        "find_notified_guest_by_partner",
                        [partnerId]
                    );
                    if (guest && guest.id) {
                        isAutoAssigned = true;
                    }
                }

                if (!isAutoAssigned && sourceTable) {
                    const tableIds = [sourceTable.id];
                    if (destOrder?.table_id?.id) tableIds.push(destOrder.table_id.id);
                    const checkResult = await this.data.call(
                        "pos.guest.queue",
                        "check_table_has_notified_guest",
                        [tableIds]
                    );
                    if (checkResult) {
                        isAutoAssigned = true;
                    }
                }
            } catch (e) {
            }
        }

        const result = await super.mergeOrders(...arguments);

        // For auto-assigned orders: Keep source table occupied
        if (isAutoAssigned === true && sourceTable) {
            const destOrderId = destOrder?.uuid || destOrder?.id;
            if (destOrderId) {
                _mergedSourceTables.set(sourceTable.id, destOrderId);
            }

            // Create placeholder order if source table has no orders
            const existingOrders = this.getTableOrders(sourceTable.id);
            if (!existingOrders.length) {
                const newOrder = this.addNewOrder({ table_id: sourceTable });
                newOrder.setBooked(true);
                newOrder.uiState._guestQueueAutoAssigned = true;
                this.addPendingOrder([newOrder.id]);
                await this.syncAllOrders({ orders: [newOrder] });
            }
        }

        return result;
    },

    /**
     * Auto-mark guest as seated when first product is added to order
     */
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
                }
            }
        } catch (e) {
        }
        return result;
    },
});

export { _mergedSourceTables };