/** @odoo-module **/
import { BaseOptionComponent } from "@html_builder/core/utils";
import { useDynamicSnippetOption } from "@website/builder/plugins/options/dynamic_snippet_hook";
import { onWillStart, useState } from "@odoo/owl";

export class DynamicSnippetDoctorsOption extends BaseOptionComponent {
    static template = "hospital_management.DynamicSnippetDoctorsOption";
    static dependencies = ["dynamic_doctor_carousel_plugin"];
    static selector = ".s_hospital_doctor_card";

    setup() {
        super.setup();
        const { fetchSpecializations, getModelNameFilter } = this.dependencies.dynamic_doctor_carousel_plugin;
        
        this.dynamicOptionParams = useDynamicSnippetOption(getModelNameFilter());

        this.state = useState({ 
            specializations: [], 
        });

        onWillStart(async () => {
            debugger
            const data = await fetchSpecializations();
            if (data) {
                this.state.specializations = data;
            }


        });

        this.templateKeyState = useDomState((el) => ({
            templateKey: el.dataset.templateKey,
        }));
    }
}