/** @odoo-module **/

import { ReceiptHeader } from "@point_of_sale/app/screens/receipt_screen/receipt/receipt_header/receipt_header";
import { patch } from "@web/core/utils/patch";

patch(ReceiptHeader.prototype, {

    get deliveryDate() {
        const order = this.props.order;

        if (order && order.estimated_delivery_final) {
            let date = new Date(order.estimated_delivery_final);

            return date.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
        }

        return "";
    },

});
