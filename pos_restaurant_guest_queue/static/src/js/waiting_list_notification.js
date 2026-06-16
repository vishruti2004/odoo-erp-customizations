import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { GuestAssignPopup } from "./guest_assign_popup";
import { _mergedSourceTables } from "./pos_store_patch";

patch(OrderSummary.prototype, {
    async unbookTable() {
        const table = this.pos.selectedTable;

        // Merge check
        if (_mergedSourceTables.has(table?.id)) {
            const destOrderId = _mergedSourceTables.get(table.id);
            const destOrder = this.pos.models["pos.order"].find(
                o => o.uuid === destOrderId || o.id === destOrderId
            );
            const destTableNumber = destOrder?.table_id?.table_number || "destination table";
            this.env.services.notification.add(
                `Table ${table.table_number} is merged with Table ${destTableNumber}. Release Table ${destTableNumber} first.`,
                { title: "Cannot Release", type: "warning" }
            );
            return;
        }

        await super.unbookTable(...arguments);

        // Merged source tables cleanup
        for (const [sourceTableId, destOrderId] of _mergedSourceTables.entries()) {
            const destOrder = this.pos.models["pos.order"].find(
                o => (o.uuid === destOrderId || o.id === destOrderId) && !o.finalized
            );
            if (!destOrder) {
                const sourceOrders = this.pos.getTableOrders(sourceTableId);
                const emptyOrders = sourceOrders.filter(o => !o.finalized && o.lines.length === 0);
                if (emptyOrders.length) {
                    await this.pos.deleteOrders(emptyOrders);
                }
                _mergedSourceTables.delete(sourceTableId);
            }
        }

        const sessionId = this.pos.session?.id;
        if (!sessionId) return;

        // Config fetch
        let sessionConfig = { auto_assign: false, waiting_duration: 5 };
        try {
            const allConfig = await this.pos.data.call("pos.guest.queue", "get_pos_config", []);
            if (allConfig?.opened_sessions) {
                const mySession = allConfig.opened_sessions.find(s => s.id === sessionId);
                if (mySession) {
                    sessionConfig = {
                        auto_assign: mySession.auto_assign || false,
                        waiting_duration: mySession.waiting_duration || 5,
                    };
                }
            }
        } catch (e) {}

        // Auto assign flow
        if (sessionConfig.auto_assign) {
            const assignedGuests = await this.pos.data.call(
                "pos.guest.queue",
                "auto_assign_all_waiting_guests",
                [sessionId]
            );

            if (assignedGuests?.length) {
                await this.pos.syncAllOrders();
                for (const assigned of assignedGuests) {
                    this.env.services.notification.add(
                        `Auto-assigned: ${assigned.guest_name} (${assigned.waiting_list_id}) — Table ${assigned.table_numbers.join(", ")}`,
                        { title: "Guest Auto Assigned", type: "success" }
                    );

                    for (const tableId of assigned.table_ids) {
                        const order = this.pos.getTableOrders(tableId).find(o => !o.finalized);
                        if (order) order.is_guest_queue_auto_assigned = true;
                    }

                    if (assigned.partner_id) {
                        setTimeout(async () => {
                            let partner = this.pos.models["res.partner"].get(assigned.partner_id);
                            if (!partner) {
                                await this.pos.data.read("res.partner", [assigned.partner_id], ["id", "name", "phone"]);
                                partner = this.pos.models["res.partner"].get(assigned.partner_id);
                            }
                            if (partner) {
                                for (const tableId of assigned.table_ids) {
                                    const order = this.pos.getTableOrders(tableId).find(o => !o.finalized);
                                    if (order) {
                                        order.setPartner(partner);
                                        this.pos.addPendingOrder([order.id]);
                                    }
                                }
                            }
                        }, 500);
                    }
                }
            }
            return;
        }

        // Waiter manual flow
        let allTables = [];
        try {
            allTables = await this.pos.data.call("pos.guest.queue", "get_available_tables_for_guest", [sessionId]);
        } catch (error) { return; }

        if (!allTables || allTables.type === "none" || !allTables.tables.length) return;

        const allTableIds = allTables.tables.map(t => t.id);
        let bestGuest = null;
        try {
            bestGuest = await this.pos.data.call("pos.guest.queue", "find_best_guest_for_tables", [allTableIds, sessionId]);
        } catch (error) { return; }

        if (!bestGuest?.guest_name) return;

        const closeNotification = this.env.services.notification.add(
            `Table ${table?.table_number} is now available.\nNext Guest: ${bestGuest.guest_name} (${bestGuest.waiting_list_id}) — ${bestGuest.party_size} Guests`,
            { title: "Guest Waiting List", type: "success", sticky: true }
        );

        setTimeout(() => {
            const notifications = document.querySelectorAll(".o_notification");
            const lastNotif = notifications[notifications.length - 1];
            if (lastNotif) {
                lastNotif.style.cursor = "pointer";
                lastNotif.addEventListener("click", () => {
                    closeNotification();
                    this.env.services.dialog.add(GuestAssignPopup, {
                        pos: this.pos,
                        availableTables: allTables.tables,
                        tableType: "combination",
                        bestGuest: bestGuest,
                        releasedTableId: table?.id,
                        waitingDuration: sessionConfig.waiting_duration || 5,
                        sessionId: sessionId,
                    });
                }, { once: true });
            }
        }, 100);
    },
});