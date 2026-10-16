/** @odoo-module **/

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { categoryLayoutState } from "@pos_category_layout/app/components/category_selector/category_selector";

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.categoryLayoutUi = useState(categoryLayoutState);
    },

    get isCustomLayout() {
        return Boolean(this.pos.config.enable_custom_layout);
    },

    get isCategorySidebar() {
        return (
            this.isCustomLayout &&
            this.pos.config.category_layout === "sidebar" &&
            !this.pos.isSmallProductScreen
        );
    },

    get categoryLayoutClasses() {
        if (!this.isCustomLayout) {
            return {};
        }
        const config = this.pos.config;
        return {
            o_pcl_scope: true,
            o_pos_cat_sidebar_mode: this.isCategorySidebar,
            o_pos_cat_sidebar_right:
                this.isCategorySidebar && config.category_sidebar_position === "right",
            o_pos_cat_sidebar_collapsed: this.isCategorySidebar && this.categoryLayoutUi.collapsed,
        };
    },

    get categoryLayoutStyle() {
        if (!this.isCustomLayout) {
            return "";
        }
        const font = String(this.pos.config.font_family || "Lato")
            .replace(/_/g, " ")
            .replace(/[^\w\s-]/g, "");
        return `--pcl-font:"${font}"`;
    },
});
