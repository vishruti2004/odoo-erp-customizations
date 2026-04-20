//** @odoo-module **/
// import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { DeliveryBoyList } from "@pos_default_customer/js/delivery_boy_userlist";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";

patch(ControlButtons.prototype, {
    async openDeliveryBoyList() {
        console.log("LOG 1: Button Clicked - Opening Delivery Boy List");

        const result = await makeAwaitable(this.dialog, DeliveryBoyList, {
            deliveryBoy: this.pos.selectedDeliveryBoy,
            onSelect: (boy) => {
                console.log("LOG 4: Data received onSelect:", boy);
                
                if (this.pos && this.pos.setDeliveryBoy) {
                    this.pos.setDeliveryBoy(boy);
                } else {
                    this.pos.selectedDeliveryBoy = boy;
                    // window.posStore = this.pos;
                }
                
                console.log("LOG 5: After setDeliveryBoy - selectedDeliveryBoy:", this.pos.selectedDeliveryBoy);
                this.render();
            }
        });
    }
});