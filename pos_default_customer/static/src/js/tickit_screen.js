/** @odoo-module **/
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

patch(TicketScreen.prototype, {
    setup() {
        super.setup(...arguments);
    },

    getDeliveryDate(order) {
        if (!order || !order.estimated_delivery_final) return "-";
        const dateStr = order.estimated_delivery_final.replace(' ', 'T');
        const dateObj = luxon.DateTime.fromISO(dateStr);
        return dateObj.isValid ? this.pos.getDate(dateObj) : "-";
    },

    getDeliveryTime(order) {
        if (!order || !order.estimated_delivery_final) return "";
        const dateStr = order.estimated_delivery_final.replace(' ', 'T');
        const dateObj = luxon.DateTime.fromISO(dateStr);
        return dateObj.isValid ? this.pos.getTime(dateObj) : "";
    }
});