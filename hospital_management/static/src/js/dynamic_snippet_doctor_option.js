/** @odoo-module **/
import { BaseOptionComponent } from "@html_builder/core/utils";
import { useDynamicSnippetOption } from "@website/builder/plugins/options/dynamic_snippet_hook";
import { onWillStart, useState } from "@odoo/owl";
import { useDomState } from "@web/core/utils/hooks";

export class DynamicSnippetDoctorsOption extends BaseOptionComponent {
    static template = "hospital_management.DynamicSnippetDoctorsOption";
    static dependencies = ["dynamic_doctor_carousel_plugin"];
    static selector = ".s_dynamic_snippet_doctor_card";

    setup() {
        super.setup();
        const { fetchSpecializations, getModelNameFilter } = this.dependencies.dynamic_doctor_carousel_plugin;
        
        this.dynamicOptionParams = useDynamicSnippetOption(getModelNameFilter());

        this.state = useState({ 
            specializations: [], 
        });

        onWillStart(async () => {
            const data = await fetchSpecializations();
            if (data) {
                this.state.specializations = data;
            }
        });

        this.templateKeyState = useDomState((el) => ({
            templateKey: el.dataset.templateKey,
        }));
    }

    get isDoctorModel() {
        return this.props.snippet.dataset.model === 'hospital.doctor';
    }
}