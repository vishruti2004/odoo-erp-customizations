import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import { patch } from "@web/core/utils/patch";

console.log("js runing");

patch(OrderPaymentValidation.prototype, {
    async afterOrderValidation(suggestToSync = true) {

        console.log("===== TABLE INFO =====");
        console.log("Table Object:", this.order.table_id);
        console.log("Table ID:", this.order.table_id?.id);
        console.log("Table Number:", this.order.table_id?.table_number);
        console.log("Seats:", this.order.table_id?.seats);

        return await super.afterOrderValidation(...arguments);
    },
});