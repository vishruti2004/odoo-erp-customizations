/** @odoo-module **/

import { CartService } from '@website_sale/js/cart_service';
import { patch } from '@web/core/utils/patch';
import { ComboConfiguratorDialog } from './combo_configurator_dialog';

patch(CartService.prototype, {
    async add(productData, options = {}) {
        if (productData.isCombo) {
            return super.add(productData, options);
        }
        if (!productData.productTemplateId) {
            return super.add(productData, options);
        }
        try {
            const checkResult = await this.rpc('/website_selection_combo/check_combo', {
                product_tmpl_id: productData.productTemplateId,
            });
            if (checkResult && checkResult.is_combo === true) {
                return this._handleSelectionCombo(productData, options);
            }
        } catch (error) {}
        return super.add(productData, options);
    },

    async _handleSelectionCombo(productData, options) {
        try {
            const comboData = await this.rpc('/website_selection_combo/get_combo_data', {
                product_tmpl_id: productData.productTemplateId,
            });
            if (comboData.error || !comboData.combos || comboData.combos.length === 0) {
                return super.add(productData, options);
            }
            return new Promise((resolve) => {
                this.dialog.add(ComboConfiguratorDialog, {
                    productId: productData.productId,
                    productTmplId: productData.productTemplateId,
                    displayName: comboData.display_name || 'Combo Product',
                    combos: comboData.combos,
                    currencyId: comboData.currency_id,
                    price: comboData.base_price || 0,
                    quantity: productData.quantity || 1,
                    save: async (selectedItems) => {
                        const result = await this._makeRequest({
                            productTemplateId: productData.productTemplateId,
                            productId: productData.productId,
                            quantity: productData.quantity || 1,
                            combo_details: selectedItems.map((item) => ({
                                product_id: item.product_id,
                                product_name: item.product_name,
                                quantity: item.quantity,
                                extra_price: item.extra_price || 0,
                            })),
                            shouldRedirectToCart: options.redirectToCart || false,
                        });
                        resolve(result);
                    },
                    close: () => {
                        resolve(0);
                    },
                });
            });
        } catch (error) {
            return super.add(productData, options);
        }
    },
});