/** @odoo-module **/

import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class DoctorListSnippet extends Interaction {
    static selector = ".s_doctor_list";
    dynamicContent = true;

    setup() {
        console.log("!!! SNIPPET DROPPED/LOADED !!!");
        this.start();
    }

    async start() {
        console.log("!!! SNIPPET STARTING !!!");
        await this._fetchCards();
        this._observeClassChanges();
    }

    async _fetchCards() {
        const container = this.el.querySelector(".o_doctor_container");
        if (!container) return;

        let specId = '0';
        for (const cls of this.el.classList) {
            if (cls.startsWith("doctor-filter-")) {
                specId = cls.replace("doctor-filter-", "");
            }
        }

        try {
            const result = await rpc('/hospital/get_filtered_doctors', {
                spec_id: specId
            });

            if (result && result.html) {
                container.innerHTML = result.html;
                console.log("!!! CARDS RENDERED !!!");
            }

        } catch (e) {
            console.error("RPC Error:", e);
        }
    }

    _observeClassChanges() {
        if (this._observer) this._observer.disconnect();
        this._observer = new MutationObserver(() => this._fetchCards());
        this._observer.observe(this.el, { attributes: true, attributeFilter: ["class"] });
    }
}


registry.category("public.interactions").add("hospital_management.doctor_list", DoctorListSnippet);
registry.category("public.interactions.edit").add("hospital_management.doctor_list", {Interaction:DoctorListSnippet});

