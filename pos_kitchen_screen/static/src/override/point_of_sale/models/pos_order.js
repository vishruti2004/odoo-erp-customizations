import { patch } from "@web/core/utils/patch";
import { PosOrder } from "@point_of_sale/app/models/pos_order";

patch(PosOrder.prototype, {
    get kitchenLocked() {
        return Boolean(this.uiState?.kitchen_locked);
    },
});
