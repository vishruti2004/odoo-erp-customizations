/** @odoo-module **/

// import { PosStore } from "@point_of_sale/app/services/pos_store";
// import { patch } from "@web/core/utils/patch";

// patch(PosStore.prototype, {
//     async afterProcessServerData() {
//         const result = await super.afterProcessServerData(...arguments);
        
//         // Order levo
//         const order = this.getOrder();
        
//         // Check karo ke order che, customer nathi, ane login user che
//         if (order && !order.partner_id && this.user && this.user.partner_id) {
//             // Login user nu partner lavo
//             let partner = null;
            
//             if (this.user.partner_id.id) {
//                 partner = this.user.partner_id;
//             } else if (this.user.partner_id[0]) {
//                 partner = this.models["res.partner"].get(this.user.partner_id[0]);
//             }
            
//             // Partner set karo
//             if (partner) {
//                 order.setPartner(partner);
//             }
//         }
        
//         return result;
//     }
// });

/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
debugger;

patch(PosStore.prototype, {
    // when pos is load this method is run 
    async afterProcessServerData() {
        debugger;
        const result = await super.afterProcessServerData(...arguments);
        this._setDefaultCustomer();
        return result;
    },
    
    // when new order is create
    addNewOrder(data = {}) {
        debugger;
        const order = super.addNewOrder(...arguments);
        this._setDefaultCustomer();
        return order;
    },
    
    //set login user into customer box
    _setDefaultCustomer() {
        debugger
        const order = this.getOrder();
        console.log(order);
        
        if (order && !order.partner_id && this.user && this.user.partner_id) {
            let partner = null;
            
            if (this.user.partner_id.id) {
                partner = this.user.partner_id;
            } else if (this.user.partner_id[0]) {
                partner = this.models["res.partner"].get(this.user.partner_id[0]);
            }
            
            if (partner) {
                order.setPartner(partner);
            }
        }
    }
});