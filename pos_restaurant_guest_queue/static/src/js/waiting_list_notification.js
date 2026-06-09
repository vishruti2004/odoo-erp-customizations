import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { GuestAssignPopup } from "./guest_assign_popup";

console.log("Waiting List Notification JS Loaded");

patch(OrderSummary.prototype, {
    async unbookTable() {
        const table = this.pos.selectedTable;

        await super.unbookTable(...arguments);

        let allTables = [];
        try {
            allTables = await this.pos.data.call(
                "pos.guest.queue",
                "get_available_tables_for_guest",
                [0]
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
                "pos.guest.queue",
                "find_best_guest_for_tables",
                [allTableIds]
            );
        } catch (error) {
            console.error("Error finding best guest:", error);
        }

        if (!bestGuest) {
            this.env.services.notification.add(
                `Table ${table.table_number} is now available. No eligible guests.`,
                { title: "Guest Waiting List", type: "warning" }
            );
            return;
        }

        let guestTableData = null;
        try {
            guestTableData = await this.pos.data.call(
                "pos.guest.queue",
                "get_available_tables_for_guest",
                [bestGuest.party_size]
            );
        } catch (error) {
            console.error("Error fetching guest table data:", error);
            return;
        }

        if (!guestTableData || guestTableData.type === "none") return;

        this.env.services.notification.add(
            `Table ${table.table_number} is now available.\n`,
            { title: "Guest Waiting List", type: "success", sticky: true }
        );

        setTimeout(() => {
            const notifications = document.querySelectorAll(".o_notification");
            const lastNotif = notifications[notifications.length - 1];
            if (lastNotif) {
                lastNotif.style.cursor = "pointer";
                lastNotif.addEventListener("click", () => {
                    this.env.services.dialog.add(GuestAssignPopup, {
                        pos: this.pos,
                        availableTables: guestTableData.tables,
                        tableType: guestTableData.type,
                        bestGuest: bestGuest,
                        releasedTableId: table.id,
                    });
                }, { once: true });
            }
        }, 100);
    },
});