/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { FormRenderer } from "@web/views/form/form_renderer";



patch(FormController.prototype, {
    get className() {
        const result = super.className;
        if (this.env.inSplitView) {
            delete result["o_xxl_form_view h-100"];
        }
        return result;
    },
});

patch(FormRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        if (!this.env.inSplitView) {
            return;
        }
        const original = this.mailLayout ? this.mailLayout.bind(this) : null;
        if (!original) {
            return;
        }
        this.mailLayout = (...args) => {
            const layout = original(...args);
            switch (layout) {
                case "SIDE_CHATTER":
                case "COMBO":
                    return "BOTTOM_CHATTER";
                case "EXTERNAL_COMBO_XXL":
                    return "EXTERNAL_COMBO";
                default:
                    return layout;
            }
        };
    },
});