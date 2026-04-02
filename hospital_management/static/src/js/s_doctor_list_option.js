/** @odoo-module **/

import { registry } from "@web/core/registry";
import { ThemeTabPlugin } from "@website/builder/plugins/theme/theme_tab_plugin";
import { BaseOptionComponent } from "@html_builder/core/utils";
import { withSequence } from "@html_editor/utils/resource";
import { OPTION_POSITIONS } from "@website/builder/plugins/theme/theme_tab_plugin";
import { theme_options} from "@website/builder/plugins/theme/theme_tab_plugin";

console.log(" JS LOADED");

// class CustomThemeTabPlugin extends ThemeTabPlugin {
//     static id = "customThemeTab";

//     // constructor() {
//     //     super(...arguments);
//     //     console.log(" Plugin Initialized");
//     // }

   
//     // get resources() {
//     //     const res = super.resources;

//     //     if (!res || !res.theme_options) {
//     //         return res || {};
//     //     }

//     //     res.theme_options.push(
//     //         withSequence(
//     //             (OPTION_POSITIONS.ADVANCED || 80) + 5,
//     //             this.getThemeOptionBlock(
//     //                 "theme-doctor-specialization",
//     //                 "Doctor Specialization",
//     //                 class DoctorOption extends BaseOptionComponent {
//     //                     static template = "hospital_management.doctor_snippet_options_template";

//     //                     setup() {
//     //                         super.setup();
//     //                         console.log(" Doctor Option Setup Done");
//     //                     }
//     //                 }
//     //             )
//     //         )
//     //     );

//     //     return res;
//     // }
//     resources = {
//         ...super.resources,
//         theme_options: [
//             ...super.resources.theme_options,
//             withSequence(
//                     OPTION_POSITIONS.ADVANCED,
//                     this.getThemeOptionBlock(
//                     "theme-card",
//                     "Card Style",
//                     class ThemeCardOption extends BaseOptionComponent {
//                         static template = "hospital_management.doctor_snippet_options_template";
//                     }
//                 )
//             ),
//         ],
//     };
// }

// registry.category("website-plugins").add("customThemeTab", CustomThemeTabPlugin);

export class DoctorOption extends BaseOptionComponent {
    static template = "hospital_management.doctor_snippet_options_template";
    static dependencies = ["DoctorOption"];
    static selector = ".s_doctor_list";

    setup() {
        super.setup();
        debugger
    }
}