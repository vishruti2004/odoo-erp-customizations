// /** @odoo-module **/
// import { DynamicSnippetCarousel } from "@website/snippets/s_dynamic_snippet_carousel/dynamic_snippet_carousel";
// import { registry } from "@web/core/registry";

// export class DynamicSnippetDoctors extends DynamicSnippetCarousel {
//     static selector = ".s_dynamic_doctors"; 
  
//     getSpecializationSearchDomain() {

//         const searchDomain = [];
//         const specId = this.el.dataset.specializationId;
//         if (specId && specId !== "all") {
//             searchDomain.push(["specialization_id", "=", parseInt(specId)]);
//         }
//         return searchDomain;
//     }

//     /** @override **/
//     getSearchDomain() {
//         const searchDomain = super.getSearchDomain(...arguments);
//         searchDomain.push(...this.getSpecializationSearchDomain());
//         return searchDomain;
//     }

//     /** @override **/
//     getRpcParameters() {

//         return Object.assign(super.getRpcParameters(...arguments), {
//             'res_model': 'hospital.doctor', 
//         });
//     }
// }

// registry.category("public.interactions").add("hospital_management.dynamic_snippet_doctors", DynamicSnippetDoctors);

// registry.category("public.interactions.edit").add("hospital_management.dynamic_snippet_doctors", {
//     Interaction: DynamicSnippetDoctors,
// });

/** @odoo-module **/
import { DynamicSnippetCarousel } from "@website/snippets/s_dynamic_snippet_carousel/dynamic_snippet_carousel";
import { registry } from "@web/core/registry";

console.log("js is load");

export class DynamicSnippetDoctors extends DynamicSnippetCarousel {
    static selector = ".s_dynamic_doctors"; 

    /** @override **/
    getRpcParameters() {
        const params = super.getRpcParameters(...arguments);
        
        const newParams = Object.assign(params, {
            'res_model': 'hospital.doctor', 
        });
        
        return newParams;
    }
}
 registry.category("public.interactions").add("hospital_management.dynamic_snippet_doctors", DynamicSnippetDoctors);

registry.category("public.interactions.edit").add("hospital_management.dynamic_snippet_doctors", {
    Interaction: DynamicSnippetDoctors,
});
