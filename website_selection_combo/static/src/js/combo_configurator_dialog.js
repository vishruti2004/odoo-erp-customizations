/** @odoo-module **/

import { Component, useState } from '@odoo/owl';
import { Dialog } from '@web/core/dialog/dialog';
import { ProductCard } from './product_card';

export class ComboConfiguratorDialog extends Component {
    static template = 'website_selection_combo.ComboConfiguratorDialog';
    static components = { Dialog, ProductCard };

    static props = {
        productId: { type: Number, optional: true },
        productTmplId: { type: Number, optional: true },
        displayName: { type: String, optional: true },
        combos: Array,
        currencyId: { type: Number, optional: true },
        price: { type: Number, optional: true },
        quantity: { type: Number, optional: true },
        editMode: { type: Boolean, optional: true },
        selectedItems: { type: Array, optional: true },
        orderLineId: { type: Number, optional: true },
        save: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            selectedQuantities: new Map(),
            isAdding: false,
            totalPrice: this.props.price || 0,
            plusDisabled: new Map(),
        });

        const existingMap = {};
        for (const sel of this.props.selectedItems || []) {
            existingMap[sel.product_id] = sel.quantity;
        }

        for (const combo of this.props.combos || []) {
            const itemQuantities = {};
            const itemDisabled = {};
            for (const item of combo.combo_items || []) {
                itemQuantities[item.id] = existingMap[item.product_id] || 0;
                itemDisabled[item.id] = false;
            }
            this.state.selectedQuantities.set(combo.id, itemQuantities);
            this.state.plusDisabled.set(combo.id, itemDisabled);
        }

        this._updateTotalPrice();
        this._updatePlusDisabled();
    }

    increaseQty(comboId, itemId, maxQty) {
        const comboQuantities = this.state.selectedQuantities.get(comboId);
        if (!comboQuantities) return;
        if (this.getComboTotalQty(comboId) >= maxQty) return;

        comboQuantities[itemId] = (comboQuantities[itemId] || 0) + 1;
        this.state.selectedQuantities.set(comboId, { ...comboQuantities });
        this._updateTotalPrice();
        this._updatePlusDisabled();
    }

    decreaseQty(comboId, itemId) {
        const comboQuantities = this.state.selectedQuantities.get(comboId);
        if (!comboQuantities) return;

        const currentQty = comboQuantities[itemId] || 0;
        if (currentQty > 0) {
            comboQuantities[itemId] = currentQty - 1;
            this.state.selectedQuantities.set(comboId, { ...comboQuantities });
            this._updateTotalPrice();
            this._updatePlusDisabled();
        }
    }

    _updatePlusDisabled() {
        for (const combo of this.props.combos || []) {
            const isDisabled = this.getComboTotalQty(combo.id) >= combo.maximum_selection;
            const comboDisabled = this.state.plusDisabled.get(combo.id);
            if (comboDisabled) {
                for (const item of combo.combo_items || []) {
                    comboDisabled[item.id] = isDisabled;
                }
                this.state.plusDisabled.set(combo.id, { ...comboDisabled });
            }
        }
    }

    getPlusDisabled(comboId, itemId) {
        return this.state.plusDisabled.get(comboId)?.[itemId] || false;
    }

    _updateTotalPrice() {
        let total = this.props.price || 0;
        for (const item of this._getSelectedItems()) {
            const combo = this.props.combos.find(c => c.id === item.combo_id);
            if (combo && combo.include_selected_product_price === 'yes') {
                total += item.quantity * item.extra_price;
            }
        }
        this.state.totalPrice = total;
    }

    _getSelectedItems() {
        const selectedItems = [];
        for (const combo of this.props.combos || []) {
            const comboQuantities = this.state.selectedQuantities.get(combo.id);
            if (!comboQuantities) continue;

            for (const item of combo.combo_items || []) {
                const qty = comboQuantities[item.id] || 0;
                if (qty > 0) {
                    selectedItems.push({
                        combo_id: combo.id,
                        product_id: item.product_id,
                        product_tmpl_id: item.product_tmpl_id || this.props.productTmplId,
                        product_name: item.product_name,
                        quantity: qty,
                        extra_price: item.extra_price || 0,
                    });
                }
            }
        }
        return selectedItems;
    }

    getComboTotalQty(comboId) {
        const comboQuantities = this.state.selectedQuantities.get(comboId);
        if (!comboQuantities) return 0;
        return Object.values(comboQuantities).reduce((sum, qty) => sum + qty, 0);
    }

    isComboValid(combo) {
        const totalQty = this.getComboTotalQty(combo.id);
        return totalQty >= combo.minimum_selection && totalQty <= combo.maximum_selection;
    }

    get areAllCombosValid() {
        return (this.props.combos || []).every(combo => this.isComboValid(combo));
    }

    get formattedTotal() {
        return `$${(this.state.totalPrice || this.props.price || 0).toFixed(2)}`;
    }

    async addToCart() {
        if (!this.areAllCombosValid) return;

        this.state.isAdding = true;
        try {
            await this.props.save(this._getSelectedItems(), { quantity: this.props.quantity || 1 });
        } catch (error) {
            console.error("Error adding combo to cart:", error);
        } finally {
            this.state.isAdding = false;
            this.props.close();
        }
    }

    cancel() {
        this.props.close();
    }
}