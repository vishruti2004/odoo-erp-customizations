import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { GuestAssignPopup } from "./guest_assign_popup";
import { _mergedSourceTables } from "./pos_store_patch";

patch(OrderSummary.prototype, {
    /**
     * Handle table unbooking/release operation
     * - Blocks release of merged source tables (auto flow only)
     * - Triggers auto-assignment if enabled in config
     * - Shows manual assignment popup for waiter flow
     */
    async unbookTable() {
        const table = this.pos.selectedTable;

        // Block release if this table is a merged source (auto flow only)
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

        // Execute original unbook operation
        await super.unbookTable(...arguments);

        // Clean up merged source tables when destination is released
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

        // Get POS configuration
        let config = { auto_assign: false, waiting_duration: 5 };
        try {
            config = await this.pos.data.call("pos.guest.queue", "get_pos_config", []);
        } catch (e) {
        }

        // ========== AUTO ASSIGN FLOW ==========
        if (config.auto_assign) {
            const assignedGuests = await this.pos.data.call(
                "pos.guest.queue", "auto_assign_all_waiting_guests", []
            );

            if (assignedGuests && assignedGuests.length) {
                await this.pos.syncAllOrders();

                for (const assigned of assignedGuests) {
                    this.env.services.notification.add(
                        `Auto-assigned: ${assigned.guest_name} (${assigned.waiting_list_id}) — Table ${assigned.table_numbers.join(", ")}`,
                        { title: "Guest Auto Assigned", type: "success" }
                    );

                    // Set auto-assigned flag on all assigned tables
                    for (const tableId of assigned.table_ids) {
                        const orders = this.pos.getTableOrders(tableId);
                        const order = orders.find(o => !o.finalized);
                        if (order) {
                            order.uiState._guestQueueAutoAssigned = true;
                        }
                    }

                    // Assign partner to orders
                    if (assigned.partner_id) {
                        setTimeout(async () => {
                            let partner = this.pos.models["res.partner"].get(assigned.partner_id);
                            if (!partner) {
                                await this.pos.data.read("res.partner", [assigned.partner_id], ["id", "name", "phone"]);
                                partner = this.pos.models["res.partner"].get(assigned.partner_id);
                            }
                            if (partner) {
                                for (const tableId of assigned.table_ids) {
                                    const orders = this.pos.getTableOrders(tableId);
                                    const order = orders.find(o => !o.finalized);
                                    if (order) {
                                        order.setPartner(partner);
                                        this.pos.addPendingOrder([order.id]);
                                    }
                                }
                            }
                        }, 500);
                    }

                    // Start timer for this guest
                    this._startGuestTimer(
                        { id: assigned.guest_id, guest_name: assigned.guest_name },
                        assigned.table_ids,
                        config.waiting_duration
                    );
                }
            }
            return;
        }

        // ========== MANUAL WAITER FLOW ==========
        let allTables = [];
        try {
            allTables = await this.pos.data.call("pos.guest.queue", "get_available_tables_for_guest", [0]);
        } catch (error) {
            return;
        }

        if (!allTables || allTables.type === "none") return;

        const allTableIds = allTables.tables.map(t => t.id);

        let bestGuest = null;
        try {
            bestGuest = await this.pos.data.call("pos.guest.queue", "find_best_guest_for_tables", [allTableIds]);
        } catch (error) {
            return;
        }
        if (!bestGuest || !bestGuest.guest_name || !bestGuest.waiting_list_id) {
            return;
        }
        let guestTableData = null;
        try {
            guestTableData = await this.pos.data.call("pos.guest.queue", "get_available_tables_for_guest", [bestGuest.party_size]);
        } catch (error) {
            return;
        }

        if (!guestTableData || guestTableData.type === "none") return;

        // Show notification with next guest info
        const closeNotification = this.env.services.notification.add(
            `Table ${table?.table_number} is now available.\nNext Guest: ${bestGuest.guest_name} (${bestGuest.waiting_list_id}) — ${bestGuest.party_size} Guests`,
            { title: "Guest Waiting List", type: "success", sticky: true }
        );

        // Show assignment popup on notification click
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

    /**
     * Select best table combination for given party size
     * Priority: Exact match → Larger table → Combination
     */
    _selectBestTables(availableTables, partySize) {
        const exactMatch = availableTables.find(t => t.seats === partySize);
        if (exactMatch) return [exactMatch];

        const largerTables = availableTables.filter(t => t.seats > partySize).sort((a, b) => a.seats - b.seats);
        if (largerTables.length) return [largerTables[0]];

        const sortedTables = [...availableTables].sort((a, b) => b.seats - a.seats);
        const selected = [];
        let totalSeats = 0;

        for (const table of sortedTables) {
            if (totalSeats >= partySize) break;
            selected.push(table);
            totalSeats += table.seats;
        }

        return totalSeats >= partySize ? selected : [];
    },

    /**
     * Auto-assign guest to selected tables
     */
    async _autoAssignGuest(bestGuest, guestTableData, duration) {
        const selectedTables = this._selectBestTables(guestTableData.tables, bestGuest.party_size);

        if (!selectedTables.length) return;

        const tableIds = selectedTables.map(t => t.id);

        const partnerId = await this.pos.data.call(
            "pos.guest.queue", "assign_guest_to_table", [bestGuest.id, tableIds]
        );

        // Create orders for each assigned table
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

        // Set partner on orders after a short delay
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

    /**
     * Start timer for guest auto-cancellation
     */
    _startGuestTimer(guest, tableIds, duration) {
        const capturedPos = this.pos;
        const capturedThis = this;

        setTimeout(async () => {
            try {
                const status = await capturedPos.data.call("pos.guest.queue", "check_guest_status", [guest.id]);
                if (status !== "notified") return;

                const primaryOrders = capturedPos.getTableOrders(tableIds[0]);
                const hasOrder = primaryOrders.some(o => !o.finalized && o.lines.length > 0);

                if (hasOrder) {
                    await capturedPos.data.call("pos.guest.queue", "mark_guest_seated", [guest.id]);
                    return;
                }

                // Cancel guest notification
                await capturedPos.data.call("pos.guest.queue", "cancel_guest_notification", [guest.id]);

                // Release empty orders from all assigned tables
                for (const tableId of tableIds) {
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
                }

                if (nextGuest) {
                    const nextGuestTableData = await capturedPos.data.call(
                        "pos.guest.queue", "get_available_tables_for_guest",
                        [nextGuest.party_size]
                    );
                    if (nextGuestTableData && nextGuestTableData.type !== "none") {
                        await capturedThis._autoAssignGuest(nextGuest, nextGuestTableData, duration);
                    }
                }
            } catch (e) {
            }
        }, duration * 60 * 1000);
    },
});