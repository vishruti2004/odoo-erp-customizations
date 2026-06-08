import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import { GuestAssignPopup } from "./guest_assign_popup";

console.log("Waiting List Notification JS Loaded");

patch(OrderSummary.prototype, {
    async unbookTable() {
        const table = this.pos.selectedTable;
        let guests = [];

        try {
            guests = await this.pos.data.call(
                "pos.guest.queue",
                "get_eligible_guest_data",
                [table.seats]
            );
        } catch (error) {
            console.error("Error fetching guests:", error);
        }

        await super.unbookTable(...arguments);

        if (guests.length) {
            const message = guests
                .map((g) => `${g.waiting_list_id} - ${g.guest_name} (${g.party_size} Guests)`)
                .join("\n");

            this.env.services.notification.add(
                `Table ${table.table_number} is now available.\n\nEligible Guests:\n${message}\n\n`,
                {
                    title: "Guest Waiting List",
                    type: "success",
                    sticky: true,
                }
            );

            setTimeout(() => {
                const notifications = document.querySelectorAll(".o_notification");
                const lastNotif = notifications[notifications.length - 1];
                if (lastNotif) {
                    lastNotif.style.cursor = "pointer";
                    lastNotif.addEventListener("click", () => {
                        this.env.services.dialog.add(GuestAssignPopup, {
                            pos: this.pos,
                            tableId: table.id,
                            guests: guests,
                        });
                    }, { once: true });
                }
            }, 100);

        } else {
            this.env.services.notification.add(
                `Table ${table.table_number} is now available. No eligible guests.`,
                { title: "Guest Waiting List", type: "warning" }
            );
        }
    },
});