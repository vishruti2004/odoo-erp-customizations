/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { DeliveryBoyList } from "@pos_default_customer/js/delivery_boy_userlist";

patch(ProductScreen.prototype, {
    async openDeliveryBoyList() {
        await makeAwaitable(this.dialog, DeliveryBoyList, {
            deliveryBoy: this.pos.selectedDeliveryBoy,
            getPayload: (selectedBoy) => {
                if (selectedBoy) {
                    this.pos.selectedDeliveryBoy = selectedBoy;
                    this.render();
                }
            },
            close: () => this.dialog.close(),
        });
    }
});