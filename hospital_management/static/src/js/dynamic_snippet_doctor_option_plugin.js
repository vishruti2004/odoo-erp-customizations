/** @odoo-module **/

import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { DynamicSnippetDoctorsOption } from "./dynamic_snippet_doctor_option";
import {withSequence} from "@html_editor/utils/resource";
import {
    DYNAMIC_SNIPPET,
    setDatasetIfUndefined
} from "@website/builder/plugins/options/dynamic_snippet_option_plugin";

class DynamicDoctorOptionPlugin extends Plugin {
    static id = "dynamicDoctorOption";
    static dependencies = ["dynamicSnippetOption"];
    static shared = ["fetchSpecializations", "getModelNameFilter"]; 
    modelNameFilter = "hospital.doctor";

    resources = {
        builder_options: withSequence(DYNAMIC_SNIPPET, DynamicSnippetDoctorsOption),
        on_snippet_dropped_handlers: this.onSnippetDropped.bind(this),
    };
    setup() {
        return this.specializations = undefined;
    }


    async fetchSpecializations() {
        if (! this.specializations) {
            this.specializations = this.services.orm.searchRead(
                "hospital.specialization", 
                [], 
                ["id", "name"]
            );
        }
        return this.specializations;
    }

    getModelNameFilter() {
        debugger;
        return this.modelNameFilter;
    }

     async onSnippetDropped({ snippetEl }) {
        debugger;
        if (snippetEl.matches(DynamicSnippetDoctorsOption.selector)) {
            setDatasetIfUndefined(snippetEl, "specializationId", -1);
            await this.dependencies.dynamicSnippetOption.setOptionsDefaultValues(
                snippetEl,
                this.modelNameFilter
            );
        }
    }
}

registry.category("website-plugins").add(DynamicDoctorOptionPlugin.id, DynamicDoctorOptionPlugin);