/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";

patch(PosStore.prototype, {
   
    selectPartner() {
        const currentOrder = this.get_order();
        
        if (currentOrder && !currentOrder.getPartner()) {
            if (this.user && this.user.partner_id) {
                const partnerId = this.user.partner_id[0];
                const partner = this.models["res.partner"]?.get(partnerId);
                
                if (partner) {
                    currentOrder.setPartner(partner);
                    console.log("Default customer set:", partner.name);
                    return; 
                }
            }
        }
        
        super.selectPartner(...arguments);
    }
});