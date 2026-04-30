/** @odoo-module **/

import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

async function checkAndRestrict(orm) {
    try {
        console.log("Restriction Service: Fetching info from server...");
        const result = await orm.call("ir.http", "get_attendance_restriction_info", []);
        
        console.log("Restriction Service: Server Response ->", result);

        if (result.enabled && !result.checked_in) {
            console.log("Restriction Service: User is Checked-Out. Showing Overlay.");
            showOverlay(result.message);
        } else {
            console.log("Restriction Service: Access Granted (Admin, Disabled, or Checked-In).");
            removeOverlay();
        }
    } catch (e) {
        console.error("Restriction Service: RPC Call Failed!", e);
    }
}

const attendanceRestrictionService = {
    dependencies: ["orm"],
    async start(env, { orm }) {
        console.log("Restriction Service: Started.");
        await checkAndRestrict(orm);
    },
};

registry.category("services").add("attendance_restriction", attendanceRestrictionService);

patch(ActivityMenu.prototype, {
    async checking() {
        console.log("Attendance Menu: checking() method called.");
        await super.checking(...arguments);
        
        console.log("Attendance Menu: Checking restriction after action...");
        const result = await this.env.services.orm.call("ir.http", "get_attendance_restriction_info", []);
        
        console.log("Attendance Menu: New Status ->", result);
        if (result.enabled && !result.checked_in) {
            showOverlay(result.message);
        } else {
            removeOverlay();
        }
    }
});

function showOverlay(message) {
    if (document.getElementById("att_restriction_overlay")) return;

    const div = document.createElement("div");
    div.id = "att_restriction_overlay";
    div.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0,0,0,0.8); z-index: 999999;
        display: flex; align-items: center; justify-content: center;
        backdrop-filter: blur(4px);
    `;

    div.innerHTML = `
        <div style="
            background: #fff; border-radius: 12px; padding: 40px; 
            max-width: 550px; width: 90%; text-align: center; 
            position: relative; box-shadow: 0 15px 50px rgba(0,0,0,0.5);
        ">
            <!-- Close Button (X) -->
            <button id="close_att_overlay" style="
                position: absolute; top: 15px; right: 15px;
                background: none; border: none; font-size: 24px;
                cursor: pointer; color: #999;
            ">&times;</button>

            <h2 style="color: #d9534f; margin-bottom: 15px;">Access Restricted</h2>
            <p style="color: #444; font-size: 16px; line-height: 1.6; margin-bottom: 25px;">
                ${message}
            </p>
            
        </div>
    `;

    document.body.appendChild(div);

    document.getElementById("close_att_overlay").addEventListener("click", () => {
        removeOverlay();
    });

    document.getElementById("btn_checkin_redirect").addEventListener("click", () => {
        removeOverlay();
        console.log("Overlay closed by user to perform check-in.");
    });
}

function removeOverlay() {
    const el = document.getElementById("att_restriction_overlay");
    if (el) {
        console.log("Restriction Service: Removing Overlay.");
        el.remove();
    }
}

/** @odoo-module **/

// import { registry } from "@web/core/registry";

// function removeOverlay() {
//     const el = document.getElementById("strict_attendance_overlay");
//     if (el) {
//         el.remove();
//         document.body.style.overflow = "auto";
//     }
// }

// function showOverlay(message) {
//     if (document.getElementById("strict_attendance_overlay")) return;

//     const div = document.createElement("div");
//     div.id = "strict_attendance_overlay";
    
//     div.style.cssText = `
//         position: fixed;
//         top: 46px; 
//         left: 0;
//         width: 100vw;
//         height: calc(100vh - 46px);
//         background: rgba(255, 255, 255, 0.7);
//         backdrop-filter: blur(20px); 
//         z-index: 100;
//         display: flex;
//         align-items: center;
//         justify-content: center;
//         pointer-events: all;
//     `;

//     div.innerHTML = `
//         <div style="text-align: center; padding: 20px;">
//             <h1 style="color: #d9534f; font-size: 32px; font-weight: bold;">Access Restricted</h1>
//             <p style="font-size: 18px; color: #333; max-width: 500px; margin: 0 auto;">
//                 ${message}
//             </p>
//             <div style="margin-top: 30px; font-weight: bold; color: #008784; font-size: 20px;">
//             </div>
//         </div>
//     `;

//     document.body.appendChild(div);
//     document.body.style.overflow = "hidden"; 
// }

// async function forceCheckAttendance(orm) {
//     try {
//         const result = await orm.call("ir.http", "get_attendance_restriction_info", []);
//         if (result.enabled && !result.checked_in) {
//             showOverlay(result.message);
//         } else {
//             removeOverlay();
//         }
//     } catch (e) {
//         console.error("Attendance Check Failed", e);
//     }
// }

// const attendanceRestrictionService = {
//     dependencies: ["orm"],
//     async start(env, { orm }) {
//         await forceCheckAttendance(orm);
//         setInterval(async () => {
//             await forceCheckAttendance(orm);
//         }, 2000);
//     },
// };

// registry.category("services").add("attendance_restriction", attendanceRestrictionService);