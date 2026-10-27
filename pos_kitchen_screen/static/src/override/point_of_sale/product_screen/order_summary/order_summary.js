import { patch } from "@web/core/utils/patch";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";

patch(OrderSummary.prototype, {
    async updateSelectedOrderline() {
        if (this.currentOrder?.kitchenLocked) {
            this.numberBuffer.reset();
            return;
        }
        return super.updateSelectedOrderline(...arguments);
    },
});
