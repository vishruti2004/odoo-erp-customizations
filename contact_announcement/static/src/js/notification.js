/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("services").add("contact_announcement_browser_notification", {
    dependencies: ["bus_service"],

    start(env, { bus_service }) {

        // Ask permission browser
        if ("Notification" in window && Notification.permission !== "granted") {
            Notification.requestPermission();
        }

        //backend notification listen
        bus_service.addEventListener("notification", ({ detail }) => {

            for (const notif of detail) {

                const type = notif.type || notif.message?.type;
                const payload = notif.payload || notif.message?.payload;

                if (type === "contact_announcement") {

                    if ("Notification" in window && Notification.permission === "granted") {

                        new Notification(payload.title || "Announcement", {
                            body: payload.message || "",
                        });
                    }
                }
            }
        });
    },
});