/** @odoo-module **/
import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { DynamicSnippetDoctorsOption } from "./dynamic_snippet_doctor_option"; 
import { withSequence } from "@html_editor/utils/resource";
import { DYNAMIC_SNIPPET_CAROUSEL } from "@website/builder/plugins/options/dynamic_snippet_carousel_option_plugin";

class DynamicDoctorOptionPlugin extends Plugin {
    static id = "dynamic_doctor_carousel_plugin";
    static dependencies = ["dynamicSnippetOption", "dynamicSnippetCarouselOption"];
    static shared = ["fetchSpecializations", "getModelNameFilter"];
    
    modelNameFilter = "hospital.doctor";

    resources = {
        builder_options: withSequence(DYNAMIC_SNIPPET_CAROUSEL, DynamicSnippetDoctorsOption),
        on_snippet_dropped_handlers: this.onSnippetDropped.bind(this),
    };

    setup() {
        this.specializations = undefined;
    }
    getModelNameFilter() {
        return this.modelNameFilter;
    }

    async fetchSpecializations() {
        if (!this.specializations) {
            this.specializations = await this.services.orm.searchRead(
                "hospital.specialization", [], ["id", "name"], { order: "name asc" }
            );
        }
        return this.specializations;
    }


    async onSnippetDropped({ snippetEl }) {
        if (snippetEl.matches(DynamicSnippetDoctorsOption.selector)) {
            await this.dependencies.dynamicSnippetCarouselOption.setOptionsDefaultValues(
                snippetEl, this.modelNameFilter, []
            );
        }
    }

    // async onSnippetDropped({ snippetEl }) {
    // if (snippetEl.matches(".s_hospital_doctor_card")) {
    //     setDatasetIfUndefined(snippetEl, "previewId", "hospital_management.s_dynamic_doctors_preview_data");

    //     await this.dependencies.dynamicSnippetOption.setOptionsDefaultValues(
    //         snippetEl,
    //         "hospital.doctor"
    //     );
        
    //     delete snippetEl.dataset.filterId;
    // }
// }
}

registry.category("website-plugins").add(DynamicDoctorOptionPlugin.id, DynamicDoctorOptionPlugin);