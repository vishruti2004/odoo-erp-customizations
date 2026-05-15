/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { renderToElement } from "@web/core/utils/render";

registry.category("services").add("contact_announcement_portal_service", {
    dependencies: ["bus_service"],

    async start(env, { bus_service }) {
        if (window.location.pathname === "/web/login") return;

        const session = await rpc("/web/session/get_session_info");
        const partnerId = session?.partner_id;
        if (!partnerId) return;

        bus_service.addChannel(`contact_announcement_${partnerId}`);

        const notificationList = document.getElementById("portal_notification_list");
        const notificationCount = document.getElementById("portal_notification_count");

        // Load existing notifications
        const existingNotifications = await rpc("/portal/notifications");

        if (notificationList && existingNotifications.length) {
            notificationList.innerHTML = "";
            const unreadCount = existingNotifications.filter(n => !n.is_read).length;
            if (notificationCount) notificationCount.innerText = unreadCount;

            existingNotifications.forEach((notif) => {
                this.renderAndAppend(notif, notificationList, notificationCount);
            });
        }

        // Real-time bus subscription
        bus_service.subscribe("contact_announcement", (payload) => {
            const tempDiv = document.createElement("div");
            tempDiv.innerHTML = payload.message || "";
            payload.message = tempDiv.textContent || tempDiv.innerText || "";

            // Browser Notification
            if (Notification.permission === "granted") {
                new Notification(payload.title, { body: payload.message });
            }

            if (!notificationList || !notificationCount) return;

            if (notificationList.querySelector(".text-center")) notificationList.innerHTML = "";
            
            // Render and Prepend
            this.renderAndAppend(payload, notificationList, notificationCount, true);

            const current = parseInt(notificationCount.innerText || "0");
            notificationCount.innerText = current + 1;
        });
    },

    renderAndAppend(notif, container, notificationCount, prepend = false) {
        const element = renderToElement("contact_announcement.NotificationItem", {
            notif: notif,
        });

        const wrapper = element.querySelector(".notification-item");
        const markReadBtn = element.querySelector(".fa-check");

        if (wrapper && markReadBtn && markReadBtn.classList.contains("mark-read-btn")) {
            wrapper.addEventListener("mouseenter", () => {
                wrapper.style.background = "#f9fafb";
                markReadBtn.style.display = "block";
            });
            wrapper.addEventListener("mouseleave", () => {
                wrapper.style.background = "transparent";
                markReadBtn.style.display = "none";
            });

            markReadBtn.addEventListener("click", async (e) => {
                e.stopPropagation();
                try {
                    await rpc("/portal/notification/read", { notification_id: notif.id });
                    markReadBtn.classList.remove("mark-read-btn");
                    markReadBtn.style.display = "block";
                    markReadBtn.style.cursor = "default";
                    const current = parseInt(notificationCount.innerText || "0");
                    if (current > 0) notificationCount.innerText = current - 1;
                } catch (err) {
                    console.error("Failed to mark as read", err);
                }
            });
        }

        if (prepend) container.prepend(element);
        else container.appendChild(element);
    }
});