/** @odoo-module **/
import { BaseOptionComponent } from "@html_builder/core/utils";
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useState } from "@odoo/owl";

export class DoctorListOption extends BaseOptionComponent {
    static template = "hospital_management.DoctorListOption";
    static selector = ".s_doctor_list";

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.state = useState({ specializations: [] });

        onWillStart(async () => {
            const records = await this.orm.searchRead(
                "hospital.specialization", [], ["id", "name", "code"]
            );
            this.state.specializations = records;
        });
    }
}

export class DoctorListOptionPlugin extends Plugin {
    static id = "hospitalManagementDoctorListOption";
    resources = { builder_options: [DoctorListOption] };
}

registry.category("website-plugins").add(DoctorListOptionPlugin.id, DoctorListOptionPlugin);