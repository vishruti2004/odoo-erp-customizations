/** @odoo-module **/
import { BaseOptionComponent as DynamicBaseOption, useDomState } from "@html_builder/core/utils";
import { useDynamicSnippetOption } from "@website/builder/plugins/options/dynamic_snippet_hook";
import { onWillStart, useState } from "@odoo/owl";

export class DynamicSnippetDoctorsOption extends DynamicBaseOption {
    static template = "hospital_management.DoctorDynamicSnippetOptionOwl"; 
    static dependencies = ["dynamicDoctorOption"]; 
    static selector = ".s_dynamic_doctors";

    setup() {
        super.setup();
        // const { getModelNameFilter, fetchSpecializations } = this.dependencies.dynamicDoctorOption;
        const { fetchSpecializations, getModelNameFilter } = this.dependencies.dynamicDoctorOption;
        debugger;
        this.dynamicOptionParams = useDynamicSnippetOption(getModelNameFilter());
        this.state = useState({ specializations: [] });

        onWillStart(async () => {
            // const data = await fetchSpecializations();
            // if (data) this.state.specializations = data;
            this.state.specializations.push(...(await fetchSpecializations()));
        });
        this.templateKeyState = useDomState((el) => ({
            templateKey: el.dataset.templateKey,
        }));
    }
}