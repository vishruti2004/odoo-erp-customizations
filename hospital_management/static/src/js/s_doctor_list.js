/** @odoo-module **/
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class DoctorListSnippet extends Interaction {
    static selector = ".s_doctor_list";
    dynamicContent = true;

    setup() {
        this.orm = this.services.orm;
    }

    async onWillStart() {
        await this._fetchCards();
    }

    async start() {
        await this._fetchCards();
        this._observeOptionChanges();
    }

    async _fetchCards() {
        const container = this.el.querySelector(".o_doctor_container");
        if (!container) {
            console.log("Container not found");
            return;
        }

        let specCode = '0';
        const filterClass = Array.from(this.el.classList).find(c => c.startsWith("doctor-filter-"));
        if (filterClass) {
            specCode = filterClass.replace('doctor-filter-', '');
        }
        
        console.log("Fetching doctors with code:", specCode);

        container.innerHTML = '<div class="text-center p-5"><i class="fa fa-spinner fa-spin fa-2x"></i><p>Loading Doctors...</p></div>';

        try {
            const result = await this.orm.call(
                'hospital.doctor',
                'get_filtered_doctors_html',
                [specCode]
            );
            
            console.log("Response:", result);
            
            if (result && result.html) {
                container.innerHTML = result.html;
            } else {
                container.innerHTML = '<div class="text-center p-5">No Doctors Found.</div>';
            }
        } catch (error) {
            console.error("Error:", error);
            container.innerHTML = '<div class="text-center p-5 text-danger">Error loading doctors.</div>';
        }
    }

    _observeOptionChanges() {
        if (this._observer) {
            this._observer.disconnect();
        }
        
        this._observer = new MutationObserver(() => {
            console.log("Class changed, reloading...");
            this._fetchCards();
        });
        
        this._observer.observe(this.el, { 
            attributes: true, 
            attributeFilter: ["class"] 
        });
    }

    destroy() {
        if (this._observer) {
            this._observer.disconnect();
        }
        super.destroy();
    }
}

registry.category("public.interactions").add("hospital_management.doctor_list", DoctorListSnippet);