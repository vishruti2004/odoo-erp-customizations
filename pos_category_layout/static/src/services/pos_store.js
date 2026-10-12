import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

const LIST_VIEW_CLASSES = "flex-row-reverse justify-content-between m-1";

const PRODUCT_SORTERS = {
    new_arrivals: (a, b) => b.id - a.id,
    name: (a, b) => a.name.localeCompare(b.name),
    price_low_high: (a, b) => a.list_price - b.list_price || a.name.localeCompare(b.name),
    price_high_low: (a, b) => b.list_price - a.list_price || a.name.localeCompare(b.name),
};

patch(PosStore.prototype, {
    get productViewMode() {
        if (this.config.enable_custom_layout && this.config.product_show_list_view) {
            return LIST_VIEW_CLASSES;
        }
        return super.productViewMode;
    },

    getConfiguredProductSorter() {
        if (!this.config.enable_custom_layout || this.searchProductWord?.trim()) {
            return null;
        }
        return PRODUCT_SORTERS[this.config.product_sort_order] || null;
    },

    orderProductBySequenceAndFav(products) {
        const sorter = this.getConfiguredProductSorter();
        return sorter ? products.sort(sorter) : super.orderProductBySequenceAndFav(...arguments);
    },

    filterExcludedProducts(products) {
        const sorter = this.getConfiguredProductSorter();
        return super.filterExcludedProducts(sorter ? Array.from(products).sort(sorter) : products);
    },
});
