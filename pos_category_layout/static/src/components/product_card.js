import { patch } from "@web/core/utils/patch";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";

const HTML_TAGS = /<[^>]*>/g;

patch(ProductCard.prototype, {
    setup() {
        super.setup(...arguments);
        this.pclPos = usePos();
    },

    get pclConfig() {
        return this.pclPos.config;
    },

    get pclActive() {
        return Boolean(this.pclConfig.enable_custom_layout) && !this.props.isComboPopup;
    },

    get pclShowPrice() {
        return this.pclActive && Boolean(this.pclConfig.product_show_price);
    },

    get pclShowDescription() {
        return this.pclActive && Boolean(this.pclConfig.product_show_description);
    },

    get pclHasInfo() {
        return this.pclShowPrice || (this.pclShowDescription && Boolean(this.pclDescription));
    },

    get pclDescription() {
        if (!this.pclShowDescription) {
            return "";
        }
        const product = this.props.product;
        const text = product.description_sale || String(product.public_description || "");
        return text.replace(HTML_TAGS, " ").replace(/\s+/g, " ").trim();
    },

    get pclPrice() {
        if (!this.pclShowPrice) {
            return "";
        }
        const product = this.props.product;
        let price = product.list_price;
        try {
            const pricelist =
                this.pclPos.getOrder?.()?.pricelist_id || this.pclConfig.pricelist_id || false;
            const computed = product.getPrice?.(pricelist, 1, 0, false);
            if (typeof computed === "number" && !Number.isNaN(computed)) {
                price = computed;
            }
        } catch {
        }
        return this.env.utils.formatCurrency(price);
    },
});
