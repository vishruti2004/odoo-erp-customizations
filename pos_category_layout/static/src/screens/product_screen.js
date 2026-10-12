import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { categoryLayoutState } from "@pos_category_layout/components/category_selector";
import { loadFont } from "@pos_category_layout/utils/font_loader";

const HEX_COLOR = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

function readableTextColor(hex) {
    const value = hex.length === 4 ? hex.replace(/./g, (c, i) => (i ? c + c : c)) : hex;
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(value.slice(i, i + 2), 16));
    return (r * 299 + g * 587 + b * 114) / 1000 > 140 ? "#212529" : "#ffffff";
}

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.categoryLayoutUi = useState(categoryLayoutState);
        if (this.pos.config.enable_custom_layout) {
            loadFont(this.pos.config.font_family);
        }
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
            o_pcl_font: true,
            o_pcl_product_list: Boolean(config.product_show_list_view),
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
        const config = this.pos.config;
        const nameBg = HEX_COLOR.test(config.product_name_bg_color || "")
            ? config.product_name_bg_color
            : "#FFFFFF";
        const columns = Math.min(Math.max(parseInt(config.product_grid_columns) || 4, 1), 12);
        const font = String(config.font_family || "Lato")
            .replace(/_/g, " ")
            .replace(/[^\w\s-]/g, "");
        return [
            `--pcl-cols:${columns}`,
            `--pcl-name-bg:${nameBg}`,
            `--pcl-name-fg:${readableTextColor(nameBg)}`,
            `--pcl-font:"${font}"`,
        ].join(";");
    },
});
