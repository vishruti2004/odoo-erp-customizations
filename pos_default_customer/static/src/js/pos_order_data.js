/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    
    setDeliveryBoy(boy) {
        console.log("=== PosOrder.setDeliveryBoy called:", boy);
        this.delivery_boy_id = boy;
    },
    
    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        console.log(data);
                
        let selectedBoy = null;
        
        if (this.pos && this.pos.selectedDeliveryBoy) {
            selectedBoy = this.pos.selectedDeliveryBoy;
        }
        else if (window.posStore && window.posStore.selectedDeliveryBoy) {
            selectedBoy = window.posStore.selectedDeliveryBoy;
        }
        else if (this.delivery_boy_id) {
            selectedBoy = this.delivery_boy_id;
        }
        
        console.log('selectedBoy:', selectedBoy);
        
        if (selectedBoy && selectedBoy.id) {
            data.delivery_boy_id = selectedBoy.id;
            console.log('Setting delivery_boy_id:', data.delivery_boy_id);
        } else if (selectedBoy) {
            data.delivery_boy_id = selectedBoy.id || selectedBoy;
        } else {
            console.log('No delivery boy selected!');
        }
        
        return data;
    }
});