import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";

const CATEGORY_SEARCH_INPUTS = ".o_pos_cat_search_wrap, .o_pos_cat_popover_search";

patch(Navbar.prototype, {
    handleKeydown(event) {
        if (event.target?.closest?.(CATEGORY_SEARCH_INPUTS)) {
            clearTimeout(this.timeout);
            this.bufferedInput = "";
            return;
        }
        return super.handleKeydown(...arguments);
    },
});