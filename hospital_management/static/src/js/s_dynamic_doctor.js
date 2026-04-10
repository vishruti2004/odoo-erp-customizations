/** @odoo-module **/
import { DynamicSnippetCarousel } from "@website/snippets/s_dynamic_snippet_carousel/dynamic_snippet_carousel";
import { registry } from "@web/core/registry";

export class DynamicSnippetDoctors extends DynamicSnippetCarousel {
    static selector = ".s_dynamic_doctors";

    getSearchDomain() {
        const searchDomain = super.getSearchDomain(...arguments);
        const specId = this.el.dataset.specializationId;
        
        if (specId && specId !== "all" && specId !== "") {
            searchDomain.push(["specialization_id", "=", parseInt(specId)]);
        }
        
        return searchDomain;
    }
}

registry.category("public.interactions").add("hospital_management.dynamic_snippet_doctors", DynamicSnippetDoctors);
registry.category("public.interactions.edit").add("hospital_management.dynamic_snippet_doctors", {
    Interaction: DynamicSnippetDoctors,
});