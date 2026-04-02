/** @odoo-module **/

import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";

export class DoctorListOption extends BaseOptionComponent {
    static template = "hospital_management.DoctorListOption";
    static selector = ".s_doctor_list";
}

export class DoctorListOptionPlugin extends Plugin {
    static id = "hospitalManagementDoctorListOption";
    resources = {
        builder_options: [DoctorListOption],
    };
}

registry
    .category("website-plugins")
    .add(DoctorListOptionPlugin.id, DoctorListOptionPlugin);
