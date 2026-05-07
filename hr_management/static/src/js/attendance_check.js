/** @odoo-module **/
import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog"; // Dialog માટે ઉમેર્યું

// if (window.location.pathname !== '/odoo/discuss' && !window.location.pathname.includes('logout')) {
//    window.location.href = '/odoo/discuss';
// }

patch(ActivityMenu.prototype, {
    async checking() {
        await super.checking(...arguments);
        removeOverlay();
        window.location.reload(); 
    }
});

registry.category("services").add("attendance_restriction", {
    dependencies: ["orm", "dialog"],
    async start(env, { orm, dialog }) {
        
        let isDialogOpen = false;

        const validateAttendance = async () => {
            if (window.location.pathname.includes('logout')) return;

            try {
                const result = await orm.call("ir.http", "get_attendance_restriction_info", []);
                
                //  Access Restriction Overlay Logic
                if (result.enabled && !result.checked_in) {
                    showOverlay(result.message);
                } else {
                    removeOverlay();
                }

                //  Late Check-in Notification Logic
                const isAlertShown = sessionStorage.getItem('late_alert_shown');

                if (result.checked_in && result.is_late && !isAlertShown && !isDialogOpen) {
                    
                    isDialogOpen = true; 

                    dialog.add(ConfirmationDialog, {
                        title: "Late Check-in Detected",
                        body: `You checked in ${result.late_formatted} late. Please note that a late penalty may be applied as per company policy.`,
                        confirmLabel: "ok",
                        confirm: () => {
                            sessionStorage.setItem('late_alert_shown', 'true');
                            isDialogOpen = false;
                        },
                        cancel: () => {
                            isDialogOpen = false;
                        },
                    });
                }
                
                // Reset State on Check-out
                if (!result.checked_in) {
                    sessionStorage.removeItem('late_alert_shown');
                }

            } catch (error) {
                console.error("Attendance Service Error:", error);
            }
        };

        validateAttendance(); 
        setInterval(validateAttendance, 5000);
    },
});
const BLOCKED_ITEMS = ['My Preferences','Shortcuts', 'Online', 'Away', 'Do Not Disturb', 'Invisible', 'Offline'];

document.addEventListener('click', (e) => {
    if (!document.getElementById("att_restriction_overlay")) return;

    const item = e.target.closest('.o-dropdown-item, .o_navigable, a, button, span');
    if (!item) return;

    const text = item.textContent?.trim();
    
    if (BLOCKED_ITEMS.some(b => text?.includes(b))) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
    }
}, true); 

let dialogObserver = null;

function startDialogBlock() {
    if (dialogObserver) return;
    const target = document.querySelector('.o-overlay-container') || document.body;
    dialogObserver = new MutationObserver((mutations) => {
        for (const { addedNodes } of mutations) {
            for (const node of addedNodes) {
                if (node.nodeType !== 1) continue;
                const dialog = node.classList?.contains('o_dialog') ? node : node.querySelector?.('.o_dialog');
                if (dialog && (dialog.textContent?.includes('Preferences') || dialog.textContent?.includes('Settings'))) {
                    node.remove();
                    return;
                }
            }
        }
    });
    dialogObserver.observe(target, { childList: true, subtree: true });
}

function showOverlay(message) {
    if (document.getElementById("att_restriction_overlay")) return;
    startDialogBlock();

    document.querySelectorAll('.o_main_navbar > *').forEach(el => el.style.visibility = 'hidden');

    const systray = document.querySelector('.o_menu_systray');
    if (systray) {
        systray.style.visibility = 'visible';
        [...systray.children].forEach(el => el.style.visibility = 'hidden');

        const attIcon = systray.querySelector('i[aria-label="Attendance"]');
        const attParent = attIcon?.closest('button')?.closest('.o_menu_systray > *');
        if (attParent) {
            attParent.style.cssText += '; visibility:visible; pointer-events:auto; z-index:10001; position:relative;';
        }

        const profile = systray.querySelector('.o_user_menu');
        if (profile) {
            profile.style.cssText += '; visibility:visible; pointer-events:auto; z-index:10001; position:relative;';
        }
    }

    const div = document.createElement("div");
    div.id = "att_restriction_overlay";
    div.style.cssText = 'position:fixed; top:46px; left:0; width:100vw; height:calc(100vh - 46px); background:rgba(0,0,0,0.7); z-index:100; backdrop-filter:blur(8px); display:flex; align-items:center; justify-content:center; pointer-events:all;';
    div.innerHTML = `<div style="background:white; border-radius:12px; padding:40px 50px; text-align:center; box-shadow:0 10px 30px rgba(0,0,0,0.5); max-width:600px;">
        <h2 style="color:#d9534f; margin-bottom:16px;">Access Restricted</h2>
        <p style="color:#555; font-size:15px; line-height:1.6;">${message}</p>
    </div>`;
    document.body.appendChild(div);
    document.body.style.overflow = "hidden";
}

function removeOverlay() {
    if (!document.getElementById("att_restriction_overlay")) return;
    document.getElementById("att_restriction_overlay").remove();
    document.body.style.overflow = "auto";
    if (dialogObserver) { dialogObserver.disconnect(); dialogObserver = null; }

    document.querySelectorAll('.o_main_navbar > *, .o_menu_systray > *').forEach(el => {
        el.style.removeProperty('visibility');
        el.style.removeProperty('pointer-events');
        el.style.removeProperty('z-index');
        el.style.removeProperty('position');
    });
}