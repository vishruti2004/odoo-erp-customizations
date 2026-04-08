/** @odoo-module **/
import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

export class DoctorListOption extends BaseOptionComponent {
    static template = "hospital_management.DoctorListOption";
    static selector = ".s_doctor_list";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({ specializations: [] });

        this.orm.searchRead(
            "hospital.specialization", [], ["id", "name", "code"]
        ).then(records => {
            this.state.specializations = records;
            console.log("Specializations loaded:", records.length);
        }).catch(e => {
            console.warn("Specializations load failed:", e);
            this.state.specializations = [];
        });
    }

    async onChangeFilter(ev) {
        const el = this.target.el;
        Array.from(el.classList).forEach(cls => {
            if (cls.startsWith("doctor-filter-")) {
                el.classList.remove(cls);
            }
        });
        const newClass = ev.detail?.value || ev.target?.value;
        if (newClass) {
            el.classList.add(newClass);
        }
    }
}

export class DoctorListOptionPlugin extends Plugin {
    static id = "hospitalManagementDoctorListOption";
    resources = { builder_options: [DoctorListOption] };
}

registry.category("website-plugins").add(
    DoctorListOptionPlugin.id,
    DoctorListOptionPlugin
);