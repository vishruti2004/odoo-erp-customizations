/** @odoo-module **/
import { ProductCard } from "@point_of_sale/app/components/product_card/product_card";
import { patch } from "@web/core/utils/patch";

patch(ProductCard, {
    props: {
        ...ProductCard.props,
        qty_available: { type: Number, optional: true },
        free_qty: { type: Number, optional: true },
    },

    
});

patch(ProductCard.prototype, {
    setup() {
        super.setup(...arguments);
        
        console.log("Product Name:", this.props.product.display_name);
        console.log("qty_available:", this.props.product.qty_available);
        console.log("Full Product Object:", this.props.product);
    },
});