import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { KitchenPriorityDropdown } from "@pos_kitchen_screen/override/point_of_sale/kitchen_priority_dropdown/kitchen_priority_dropdown";

ControlButtons.components = { ...ControlButtons.components, KitchenPriorityDropdown };
patch(ControlButtons.prototype, {
    get kitchenPriorityAvailable() {
        return Boolean(this.pos.config?.kitchen_advanced);
    },
    onKitchenPriority(priority) {
        return this.pos.setKitchenPriority(this.pos.getOrder(), priority);
    },
});
