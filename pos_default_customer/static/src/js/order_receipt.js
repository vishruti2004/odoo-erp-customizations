/** @odoo-module **/

import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { patch } from "@web/core/utils/patch";

patch(OrderReceipt.prototype, {
    get header() {
        const original = super.header;
        const order = this.order;
        
        if (order && order.estimated_delivery_final) {
            original.cashier = original.cashier + ' | Est. Delivery: ' + order.estimated_delivery_final;
        }
        
        return original;
    }
});