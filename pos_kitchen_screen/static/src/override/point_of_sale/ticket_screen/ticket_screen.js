import { patch } from "@web/core/utils/patch";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { KitchenPriorityDropdown } from "@pos_kitchen_screen/override/point_of_sale/kitchen_priority_dropdown/kitchen_priority_dropdown";

TicketScreen.components = { ...TicketScreen.components, KitchenPriorityDropdown };
patch(TicketScreen.prototype, {
    get kitchenPriorityAvailable() {
        return Boolean(this.pos.config?.kitchen_advanced);
    },
    onKitchenPriority(order, priority) {
        return this.pos.setKitchenPriority(order, priority);
    },
});
