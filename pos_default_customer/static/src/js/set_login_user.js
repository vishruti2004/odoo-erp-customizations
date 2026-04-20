/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/services/pos_store";
import { patch } from "@web/core/utils/patch";
const { DateTime } = luxon; 
patch(PosStore.prototype, {

    // async addLineToOrder(vals, order, opts = {}, configure = true) {
        
    //     if (vals && !vals.product_id && vals.product_tmpl_id) {
    //         const productTemplate = typeof vals.product_tmpl_id === "number" 
    //             ? this.models["product.template"].get(vals.product_tmpl_id)
    //             : vals.product_tmpl_id;

    //         if (productTemplate && productTemplate.product_variant_ids.length > 0) {
    //             vals.product_id = productTemplate.product_variant_ids[0];
    //             console.log("Fixed: product_id set manually to prevent crash");
    //         }
    //     }

    //     return await super.addLineToOrder(...arguments);
    // },

    // async handleConfigurableProduct(values, productTemplate, opts = {}, configure = true) {
    //     if (!values || !values.product_id) {
    //         if (!productTemplate.isConfigurable() && productTemplate.product_variant_ids.length > 0) {
    //             values.product_id = productTemplate.product_variant_ids[0];
    //         } else {
    //             return false; 
    //         }
    //     }
    //     return super.handleConfigurableProduct(...arguments);
    // },
    
    setDeliveryBoy(boy) {
        if (!boy) {
            return;
        }
        this.selectedDeliveryBoy = boy;
        
        window.posStore = this;
        
        
        const order = this.getOrder();
        if (order && order.setDeliveryBoy) {
            order.setDeliveryBoy(boy);
        }
    },
    
    async afterProcessServerData() {


        const result = await super.afterProcessServerData(...arguments);

        this._setDefaultCustomer();
        this._setDeliveryDate(); 
        return result;

    
    },
    
    addNewOrder(data = {}) {
        const order = super.addNewOrder(...arguments);
        this._setDefaultCustomer();
        this._setDeliveryDate(); 

        
        if (this.selectedDeliveryBoy && order.setDeliveryBoy) {
            order.setDeliveryBoy(this.selectedDeliveryBoy);  
        }
        
        return order;
    },
    
    _setDefaultCustomer() {
        const order = this.getOrder();
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
    },

    _setDeliveryDate() {
        const order = this.getOrder();
        if (order && this.config && this.config.estimated_delivery_date) {
            let deliveryDate = DateTime.now(); 
            let duration = this.config.estimated_delivery_date;

            if (this.config.delivery_type === 'hours') {
                deliveryDate = deliveryDate.plus({ hours: duration });
            } else {
                deliveryDate = deliveryDate.plus({ days: duration });
            }
            
            order.estimated_delivery_final = deliveryDate;
        }
    }
});