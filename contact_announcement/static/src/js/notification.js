/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

registry.category("services").add("contact_announcement_browser_notification", {
    dependencies: ["bus_service"],

    async start(env, { bus_service }) {

        // Request browser notification permission if not  granted
        if ("Notification" in window && Notification.permission !== "granted") {
            Notification.requestPermission();
        }

        // Fetch current session to get partner ID
        const partnerId = session?.partner_id;

        if (!partnerId) {
            return;
        }

        // Subscribe to partner-specific announcement channel
        const channel = `contact_announcement_${partnerId}`;
        bus_service.addChannel(channel);

        // Listen for incoming real-time announcements
        bus_service.subscribe("contact_announcement", (payload) => {
            if ("Notification" in window && Notification.permission === "granted") {
                new Notification(payload?.title || "Announcement", {
                    body: payload?.message || "",
                });
            }
        });
    },
});