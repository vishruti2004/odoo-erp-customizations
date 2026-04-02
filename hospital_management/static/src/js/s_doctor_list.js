/** @odoo-module **/
import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class DoctorListSnippet extends Interaction {
    static selector = ".s_doctor_list";

    start() {
        this._applySpecializationFilter();
        this._observeOptionChanges();
    }

    destroy() {
        if (this._classObserver) {
            this._classObserver.disconnect();
            this._classObserver = null;
        }
        super.destroy();
    }

    _observeOptionChanges() {
        this._classObserver = new MutationObserver((mutations) => {
            const hasClassChange = mutations.some((mutation) => mutation.attributeName === "class");
            if (hasClassChange) {
                this._applySpecializationFilter();
            }
        });
        this._classObserver.observe(this.el, {
            attributes: true,
            attributeFilter: ["class"],
        });
    }

    _applySpecializationFilter() {
        const specializationId = this._getSelectedSpecializationId();
        const items = this.el.querySelectorAll(".doctor-card-item");

        if (!specializationId) {
            for (const item of items) {
                item.classList.remove("d-none");
            }
            return;
        }

        for (const item of items) {
            const shouldShow = item.dataset.specialization === specializationId;
            item.classList.toggle("d-none", !shouldShow);
        }
    }

    _getSelectedSpecializationId() {
        const filterClass = Array.from(this.el.classList).find((className) =>
            className.startsWith("doctor-filter-")
        );
        return filterClass ? filterClass.replace("doctor-filter-", "") : null;
    }
}

registry
    .category("public.interactions")
    .add("hospital_management.DoctorListSnippet", DoctorListSnippet);

registry
    .category("public.interactions.edit")
    .add("hospital_management.DoctorListSnippet", {
        Interaction: DoctorListSnippet,
    });
