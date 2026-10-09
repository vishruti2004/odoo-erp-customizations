import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";

const HEX_COLOR = /^#[0-9a-fA-F]{3,8}$/;

patch(ProductScreen.prototype, {
    /** Classes applied on the category + product container (read from the POS config). */
    get categoryLayoutClasses() {
        try {
            return this._categoryLayoutClasses();
        } catch (error) {
            console.error("[pos_category_layout] classes error", error);
            return {};
        }
    },

    _categoryLayoutClasses() {
        const config = this.pos.config;
        return {
            o_pcl_scope: true,
            [`o_pcl_card_${config.product_card_style || "standard"}`]: true,
            [`o_pcl_spacing_${config.product_card_spacing || "normal"}`]: true,
            [`o_pcl_font_${config.font_family || "default"}`]: true,
            o_pos_cat_sidebar_mode:
                config.category_layout === "sidebar" && !this.pos.isSmallProductScreen,
            o_pos_cat_sidebar_right: config.category_sidebar_position === "right",
        };
    },

    /** CSS variables carrying the configured colors / grid columns. */
    get categoryLayoutStyle() {
        try {
            return this._categoryLayoutStyle();
        } catch (error) {
            console.error("[pos_category_layout] style error", error);
            return "";
        }
    },

    _categoryLayoutStyle() {
        const config = this.pos.config;
        const color = (value, fallback) => (HEX_COLOR.test(value || "") ? value : fallback);
        const columns = Math.min(Math.max(parseInt(config.product_grid_columns) || 4, 1), 12);
        return [
            `--pcl-cols:${columns}`,
            `--pcl-primary:${color(config.primary_color, "#8CC187")}`,
            `--pcl-category-bg:${color(config.category_color, "#FFFFFF")}`,
            `--pcl-product-bg:${color(config.product_color, "#FFFFFF")}`,
        ].join(";");
    },
});
