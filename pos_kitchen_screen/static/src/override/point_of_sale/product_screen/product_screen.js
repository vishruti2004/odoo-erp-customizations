import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

patch(ProductScreen.prototype, {
    onNumpadClick() {
        if (this.currentOrder?.kitchenLocked) {
            return;
        }
        return super.onNumpadClick(...arguments);
    },
    displayAllControlPopup() {
        if (this.currentOrder?.kitchenLocked) {
            this.notification.add(
                _t("Order is ready in the kitchen and cannot be changed."),
                { type: "warning" }
            );
            return;
        }
        return super.displayAllControlPopup(...arguments);
    },
});
