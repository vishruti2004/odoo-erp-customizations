/** @odoo-module **/

import { Component } from '@odoo/owl';

export class ProductCard extends Component {
    static template = 'website_selection_combo.ProductCard';

    static props = {
        comboId: Number,
        item: Object,
        quantity: Number,
        onIncrease: Function,
        onDecrease: Function,
        maxQty: Number,
        isPlusDisabled: { type: Boolean, optional: true },
    };

    get isSelected() {
        return this.props.quantity > 0;
    }

    get formattedExtraPrice() {
        if (!this.props.item) return '';
        const price = this.props.item.extra_price || 0;
        return price > 0 ? `+ $${price.toFixed(2)}` : '';
    }

    get productImage() {
        return this.props.item?.image_url || '/web/static/img/placeholder.png';
    }

    get productName() {
        return this.props.item?.product_name || 'Unknown Product';
    }
}