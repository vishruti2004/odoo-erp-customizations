import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { GuestAssignPopup } from "./guest_assign_popup";

patch(OrderSummary.prototype, {
    async unbookTable() {
        const table = this.pos.selectedTable;

        // auto-assigned merged tables warning
        const allOrders = this.pos.models["pos.order"].filter(o => !o.finalized);
        for (const order of allOrders) {
            if (!order.uiState?._guestQueueAutoAssigned) continue;

            const mergedIds = [
                ...Object.values(order.uiState?.unmerge || {}).map(d => parseInt(d.table_id)),
                ...(order.uiState?._mergedSourceTables || [])
            ];
            if (mergedIds.includes(parseInt(table?.id))) {
                this.env.services.notification.add(
                    `Table ${table.table_number} is merged with Table ${order.table_id?.table_number}. Release Table ${order.table_id?.table_number} first.`,
                    { title: "Cannot Release", type: "warning" }
                );
                return;
            }
        }

        await super.unbookTable(...arguments);

        let config = { auto_assign: false, waiting_duration: 5 };
        try {
            config = await this.pos.data.call("pos.guest.queue", "get_pos_config", []);
        } catch (e) {
            console.error("Config fetch error:", e);
        }

        let allTables = [];
        try {
            allTables = await this.pos.data.call(
                "pos.guest.queue", "get_available_tables_for_guest", [0]
            );
        } catch (error) {
            console.error("Error fetching tables:", error);
            return;
        }

        if (!allTables || allTables.type === "none") return;

        const allTableIds = allTables.tables.map(t => t.id);

        let bestGuest = null;
        try {
            bestGuest = await this.pos.data.call(
                "pos.guest.queue", "find_best_guest_for_tables", [allTableIds]
            );
        } catch (error) {
            console.error("Error finding best guest:", error);
        }

        if (!bestGuest) {
            this.env.services.notification.add(
                `Table ${table?.table_number} is now available. No eligible guests.`,
                { title: "Guest Waiting List", type: "warning" }
            );
            return;
        }

        let guestTableData = null;
        try {
            guestTableData = await this.pos.data.call(
                "pos.guest.queue", "get_available_tables_for_guest", [bestGuest.party_size]
            );
        } catch (error) {
            console.error("Error fetching guest table data:", error);
            return;
        }

        if (!guestTableData || guestTableData.type === "none") return;

        if (config.auto_assign) {
            await this._autoAssignGuest(bestGuest, guestTableData, config.waiting_duration);
            return;
        }

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
                        availableTables: guestTableData.tables,
                        tableType: guestTableData.type,
                        bestGuest: bestGuest,
                        releasedTableId: table?.id,
                        waitingDuration: config.waiting_duration,
                    });
                }, { once: true });
            }
        }, 100);
    },

    _selectBestTables(availableTables, partySize) {
        const exactFit = availableTables.find(t => t.seats === partySize);
        if (exactFit) return [exactFit];

        const largerTables = availableTables
            .filter(t => t.seats > partySize)
            .sort((a, b) => a.seats - b.seats);
        if (largerTables.length) return [largerTables[0]];

        const sorted = [...availableTables].sort((a, b) => b.seats - a.seats);
        const selected = [];
        let totalSeats = 0;
        for (const table of sorted) {
            if (totalSeats >= partySize) break;
            selected.push(table);
            totalSeats += table.seats;
        }
        if (totalSeats >= partySize) return selected;
        return [];
    },

    async _autoAssignGuest(bestGuest, guestTableData, duration) {
        const selectedTables = this._selectBestTables(guestTableData.tables, bestGuest.party_size);

        if (!selectedTables.length) {
            console.error("No suitable tables found for guest", bestGuest);
            return;
        }

        const tableIds = selectedTables.map(t => t.id);
        const partnerId = await this.pos.data.call(
            "pos.guest.queue", "assign_guest_to_table", [bestGuest.id, tableIds]
        );

        // Table book 
        for (const tableData of selectedTables) {
            const table = this.pos.models["restaurant.table"].get(tableData.id);
            if (table) {
                const existingOrders = this.pos.getTableOrders(tableData.id);
                const activeOrder = existingOrders.find(o => !o.finalized);
                if (!activeOrder) {
                    const newOrder = this.pos.addNewOrder({ table_id: table });
                    newOrder.uiState._guestQueueAutoAssigned = true;
                } else {
                    activeOrder.uiState._guestQueueAutoAssigned = true;
                }
            }
        }

        if (partnerId) {
            setTimeout(async () => {
                let partner = this.pos.models["res.partner"].get(partnerId);
                if (!partner) {
                    await this.pos.data.read("res.partner", [partnerId], ["id", "name", "phone"]);
                    partner = this.pos.models["res.partner"].get(partnerId);
                }
                if (partner) {
                    for (const tableData of selectedTables) {
                        const orders = this.pos.getTableOrders(tableData.id);
                        const order = orders.find(o => !o.finalized);
                        if (order) {
                            order.setPartner(partner);
                            this.pos.addPendingOrder([order.id]);
                        }
                    }
                }
            }, 500);
        }

        const tableNumbers = selectedTables.map(t => `Table ${t.table_number}`).join(", ");
        const totalSeats = selectedTables.reduce((sum, t) => sum + (t.seats || 0), 0);
        this.env.services.notification.add(
            `Auto-assigned: ${bestGuest.guest_name} (${bestGuest.waiting_list_id})\n${tableNumbers} — ${totalSeats} seats for ${bestGuest.party_size} guests`,
            { title: "Guest Auto Assigned", type: "success" }
        );

        this._startGuestTimer(bestGuest, tableIds, duration);
    },

    _startGuestTimer(guest, tableIds, duration) {
        const capturedPos = this.pos;
        const capturedThis = this;

        setTimeout(async () => {
            try {
                const status = await capturedPos.data.call(
                    "pos.guest.queue", "check_guest_status", [guest.id]
                );

                if (status !== "notified") return;

                const primaryOrders = capturedPos.getTableOrders(tableIds[0]);
                const activeOrder = primaryOrders.find(o => !o.finalized && o.lines.length > 0);

                if (activeOrder) {
                    await capturedPos.data.call("pos.guest.queue", "mark_guest_seated", [guest.id]);
                    return;
                }

                await capturedPos.data.call("pos.guest.queue", "cancel_guest_notification", [guest.id]);

                for (const tableId of tableIds) {
                    const allOrders = capturedPos.models["pos.order"].filter(o => !o.finalized);
                    let isMergedSource = false;
                    let destinationTableNumber = null;

                    for (const order of allOrders) {
                        const mergedIds = [
                            ...Object.values(order.uiState?.unmerge || {}).map(d => parseInt(d.table_id)),
                            ...(order.uiState?._mergedSourceTables || [])
                        ];
                        if (mergedIds.includes(parseInt(tableId))) {
                            isMergedSource = true;
                            destinationTableNumber = order.table_id?.table_number;
                            break;
                        }
                    }

                    if (isMergedSource) {
                        capturedPos.env.services.notification.add(
                            `Table ${tableId} is merged with Table ${destinationTableNumber}. Will release when Table ${destinationTableNumber} is released.`,
                            { title: "Table Merged", type: "info" }
                        );
                        continue;
                    }

                    const orders = capturedPos.getTableOrders(tableId);
                    const emptyOrders = orders.filter(o => !o.finalized && o.lines.length === 0);
                    if (emptyOrders.length) {
                        await capturedPos.deleteOrders(emptyOrders);
                    }
                }

                let nextGuest = null;
                try {
                    nextGuest = await capturedPos.data.call("pos.guest.queue", "find_best_guest_for_tables", [tableIds]);
                } catch (e) {
                    console.error("Error finding next guest:", e);
                }

                if (nextGuest) {
                    const nextGuestTableData = await capturedPos.data.call(
                        "pos.guest.queue", "get_available_tables_for_guest", [nextGuest.party_size]
                    );
                    if (nextGuestTableData && nextGuestTableData.type !== "none") {
                        await capturedThis._autoAssignGuest(nextGuest, nextGuestTableData, duration);
                    } else {
                        capturedPos.env.services.notification.add(
                            `${guest.guest_name} did not arrive! No suitable table for next guest.`,
                            { title: "Guest Not Arrived", type: "warning" }
                        );
                    }
                } else {
                    capturedPos.env.services.notification.add(
                        `${guest.guest_name} did not arrive! No guests in waiting list.`,
                        { title: "Guest Not Arrived", type: "warning" }
                    );
                }
            } catch (e) {
                console.error("=== TIMER ERROR ===", e);
            }
        }, duration * 60 * 1000);
    },
});