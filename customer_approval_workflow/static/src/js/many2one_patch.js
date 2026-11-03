import { patch } from "@web/core/utils/patch";
import { Many2One } from "@web/views/fields/many2one/many2one";

patch(Many2One.prototype, {
    get many2XAutocompleteProps() {
        const props = super.many2XAutocompleteProps;
        if (this.props.relation !== "res.partner") {
            return props;
        }
        return {
            ...props,
            activeActions: { ...props.activeActions, create: false, createEdit: false },
            quickCreate: null,
            otherSources: [],
            getDomain: () => {
                const domain =
                    typeof props.getDomain === "function" ? props.getDomain() : props.getDomain;
                return [...(domain || []), ["state", "=", "approved"]];
            },
        };
    },
});