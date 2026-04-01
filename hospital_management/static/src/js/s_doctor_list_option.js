/** @odoo-module **/

import { DynamicSnippetOption } from "@website/builder/plugins/options/dynamic_snippet_option";
import { registry } from "@web/core/registry";

console.log(">>> Doctor JS File Loaded Successfully"); 

export class DoctorSnippetOption extends DynamicSnippetOption {
    static template = "hospital_management.DoctorSnippetOptions";
    static selector = "section.s_doctor_list";

    setup() {
        super.setup();
        console.log(">>> DoctorSnippetOption Setup Called for:", this.target);
    }

    async specialization(value) {
        console.log(">>> Specialization Changed to:", value);
        this.target.dataset.specialization = value;
        this.reset();
    }

    async columns(value) {
        console.log(">>> Columns Changed to:", value);
        this.target.dataset.columns = value;
        const grid = this.target.querySelector('.row'); 
        if (grid) {
            const classes = Array.from(grid.classList).filter(c => c.startsWith('row-cols-'));
            grid.classList.remove(...classes);
            grid.classList.add(`row-cols-${value}`);
        }
        this.reset();
    }
}

registry.category("website_snippet_options").add("hospital_doctor_option", DoctorSnippetOption);