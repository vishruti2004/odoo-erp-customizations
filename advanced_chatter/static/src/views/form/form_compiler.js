/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormCompiler } from "@web/views/form/form_compiler";
import { setAttributes } from "@web/core/utils/xml";
import { evaluateExpr } from "@web/core/py_js/py";

patch(FormCompiler.prototype, {
    setup() {
        super.setup(...arguments);

        const chatterCompiler = this.compilers.find(
            (compiler) => compiler.selector === "chatter"
        );

        if (!chatterCompiler || chatterCompiler._advancedChatterPatched) {
            return;
        }

        const originalFn = chatterCompiler.fn;

        chatterCompiler.fn = function (node, params) {
            const result = originalFn.call(this, node, params);

            if (!result || !node?.getAttribute) {
                return result;
            }

            const chatter = Array.from(
                result.querySelectorAll("t[t-component]")
            ).find((element) =>
                element.getAttribute("t-component")?.includes("Chatter")
            );

            if (!chatter) {
                return result;
            }

            const optionsAttr = node.getAttribute("options");

            if (!optionsAttr) {
                return result;
            }

            let options;

            try {
                options = evaluateExpr(optionsAttr) || {};
            } catch (error) {
                console.error("[AdvancedChatter] Invalid chatter options:", error);
                return result;
            }

            if ("advance_search" in options) {
                setAttributes(chatter, {
                    advancesearch: !!options.advance_search,
                });
            }

            if ("advance_filter" in options) {
                setAttributes(chatter, {
                    advancefilter: !!options.advance_filter,
                });
            }

            return result;
        };

        chatterCompiler._advancedChatterPatched = true;
    },
});