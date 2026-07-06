/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { registry } from '@web/core/registry';
import { rpc } from '@web/core/network/rpc';
import { ComboConfiguratorDialog } from './combo_configurator_dialog';

publicWidget.registry.CartComboEdit = publicWidget.Widget.extend({
    selector: '#cart_products',   
    events: {
        'click .combo-edit-link': '_onEditClick',  
    },

    init() {
        this._super(...arguments);
        this.dialog = this.bindService("dialog");
    },

    _onEditClick: function(ev) {
        ev.preventDefault();
        ev.stopPropagation();

        const lineId = ev.currentTarget.dataset.lineId;
        if (lineId) {
            this._openEditDialog(lineId);
        }
    },

    async _openEditDialog(lineId) {
        try {
            const lineData = await rpc('/website_selection_combo/get_order_line_data', {
                line_id: lineId,
            });

            if (!lineData || !lineData.is_combo_line) {
                return;
            }

            this.dialog.add(ComboConfiguratorDialog, {
                productId: lineData.product_id,
                productTmplId: lineData.product_tmpl_id,
                displayName: lineData.display_name || 'Edit Combo',
                combos: lineData.combos,
                currencyId: lineData.currency_id,
                price: lineData.base_price || 0,
                quantity: lineData.quantity || 1,
                editMode: true,
                selectedItems: lineData.selected_items,
                orderLineId: lineId,
                includeComboItemsPrice: lineData.include_combo_items_price,
                save: async (selectedItems, comboProductData) => {
                    await rpc('/website_selection_combo/update_order_line', {
                        line_id: lineId,
                        selected_items: selectedItems,
                        quantity: comboProductData?.quantity || 1,
                    });

                    const response = await fetch('/shop/cart', {
                        method: 'GET',
                        headers: { 'X-Requested-With': 'XMLHttpRequest' },
                    });
                    const htmlText = await response.text();
                    const parser = new DOMParser();
                    const newDoc = parser.parseFromString(htmlText, 'text/html');

                    const newCartProducts = newDoc.getElementById('cart_products');
                    const currentCartProducts = document.getElementById('cart_products');
                    if (newCartProducts && currentCartProducts) {
                        currentCartProducts.innerHTML = newCartProducts.innerHTML;
                    }

                    const newTotal = newDoc.querySelector('.o_total_card');
                    const currentTotal = document.querySelector('.o_total_card');
                    if (newTotal && currentTotal) {
                        currentTotal.innerHTML = newTotal.innerHTML;
                    }

                    const newBadge = newDoc.querySelector('.my_cart_quantity');
                    const currentBadge = document.querySelector('.my_cart_quantity');
                    if (newBadge && currentBadge) {
                        currentBadge.textContent = newBadge.textContent;
                        currentBadge.classList.toggle('d-none', newBadge.classList.contains('d-none'));
                    }
                },
                close: () => {},
            });

        } catch (error) {
            console.error("Error opening edit dialog:", error);
        }
    },
});

registry.category('publicWidgets').add('CartComboEdit', publicWidget.registry.CartComboEdit);