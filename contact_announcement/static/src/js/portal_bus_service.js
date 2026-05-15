/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

registry.category("services").add("contact_announcement_portal_service", {
    dependencies: ["bus_service"],

    async start(env, { bus_service }) {

        // Skip execution on the login page
        if (window.location.pathname === "/web/login") {
            return;
        }

        // Fetch current session to get partner ID
        const session = await rpc("/web/session/get_session_info");
        const partnerId = session?.partner_id;

        if (!partnerId) {
            return;
        }

        // Subscribe to partner-specific announcement channel
        const channel = `contact_announcement_${partnerId}`;
        bus_service.addChannel(channel);

        // Portal UI elements — only present on portal pages
        const notificationList = document.getElementById("portal_notification_list");
        const notificationCount = document.getElementById("portal_notification_count");

        // Load and render existing notifications from server
        const existingNotifications = await rpc("/portal/notifications");

        if (notificationList && existingNotifications.length) {
            notificationList.innerHTML = "";

            // Calculate and display unread count
            const unreadCount = existingNotifications.filter(notif => !notif.is_read).length;
            if (notificationCount) {
                notificationCount.innerText = unreadCount;
            }

            // Render each existing notification
            existingNotifications.forEach((notif) => {
                const item = this.createNotificationItem(notif, notificationCount);
                notificationList.appendChild(item);
            });
        }

        // Listen for incoming real-time announcements
        bus_service.subscribe("contact_announcement", (payload) => {

            // Strip HTML tags from message content
            const tempDiv = document.createElement("div");
            tempDiv.innerHTML = payload.message || "";
            const plainMessage = tempDiv.textContent || tempDiv.innerText || "";
            payload.message = plainMessage;

            // Show browser popup notification if permission is granted
            if ("Notification" in window) {
                if (Notification.permission === "granted") {
                    new Notification(payload.title || "Announcement", {
                        body: plainMessage,
                    });
                } else if (Notification.permission !== "denied") {
                    Notification.requestPermission().then((permission) => {
                        if (permission === "granted") {
                            new Notification(payload.title || "Announcement", {
                                body: plainMessage,
                            });
                        }
                    });
                }
            }

            // Skip portal UI update if not on a portal page
            if (!notificationList || !notificationCount) return;

            // Remove empty state placeholder if present
            if (notificationList.querySelector(".text-center")) {
                notificationList.innerHTML = "";
            }

            // Prepend new notification to the top of the list
            const newItem = this.createNotificationItem(payload, notificationCount);
            notificationList.prepend(newItem);

            // Increment unread count
            const current = parseInt(notificationCount.innerText || "0");
            notificationCount.innerText = current + 1;
        });
    },

    // Build and return a single notification list item element
    createNotificationItem(notif, notificationCount) {
        const item = document.createElement("div");
        item.className = "p-3 border-bottom";

        item.innerHTML = `
            <div class="notification-item">
                <div class="d-flex justify-content-between align-items-start mb-1">
                    <div class="fw-bold" style="font-size:14px; color:#374151;">
                        ${notif.title || "Update"}
                    </div>
                    <small style="font-size:11px; color:#9ca3af; white-space:nowrap;">
                        ${notif.date ? notif.date.split(",")[0] : ""}
                    </small>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <div class="text-muted small">
                        ${notif.message || ""}
                    </div>
                    ${!notif.is_read ? `
                        <i class="fa fa-check text-success mark-read-btn" style="display:none; cursor:pointer;"></i>
                    ` : `
                        <i class="fa fa-check text-success"></i>
                    `}
                </div>
            </div>
        `;

        const wrapper = item.querySelector(".notification-item");
        const markReadBtn = item.querySelector(".mark-read-btn");

        if (wrapper && markReadBtn) {

            // Show check icon on hover for unread notifications
            wrapper.addEventListener("mouseenter", () => {
                wrapper.style.background = "#f9fafb";
                if (markReadBtn.classList.contains("mark-read-btn")) {
                    markReadBtn.style.display = "block";
                }
            });

            // Hide check icon when mouse leaves
            wrapper.addEventListener("mouseleave", () => {
                wrapper.style.background = "transparent";
                if (markReadBtn.classList.contains("mark-read-btn")) {
                    markReadBtn.style.display = "none";
                }
            });

            // Mark notification as read on click
            markReadBtn.addEventListener("click", async (e) => {
                e.stopPropagation();

                // Skip if already marked as read
                if (!markReadBtn.classList.contains("mark-read-btn")) {
                    return;
                }

                try {
                    await rpc("/portal/notification/read", {
                        notification_id: notif.id,
                    });
                } catch (err) {
                    console.error("[Announcement] Mark as read failed:", err);
                }

                // Lock icon as permanently visible — remove hover behavior
                markReadBtn.classList.remove("mark-read-btn");
                markReadBtn.style.display = "block";
                markReadBtn.style.cursor = "default";

                // Decrease unread count
                if (notificationCount) {
                    const current = parseInt(notificationCount.innerText || "0");
                    if (current > 0) {
                        notificationCount.innerText = current - 1;
                    }
                }
            });
        }

        return item;
    },
});