/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { Many2One } from "@web/views/fields/many2one/many2one";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";

function isCreationRestricted(resModel) {
    const config = session.quick_create_restriction || {};
    if (!config.enabled || !resModel) {
        return false;
    }

    const restrictedModels = config.model_ids || [];
    if (!restrictedModels.length) {
        return true;
    }
    return restrictedModels.includes(resModel);
}

/* Many2one */

patch(Many2One.prototype, {
    get activeActions() {
        const relation = this.props.relation;
        if (isCreationRestricted(relation)) {
            return { ...super.activeActions, create: false, createEdit: false };
        }
        return super.activeActions;
    },

    get many2XAutocompleteProps() {
        const props = super.many2XAutocompleteProps;
        const relation = this.props.relation;
        if (isCreationRestricted(relation)) {
            return { ...props, quickCreate: null };
        }
        return props;
    },
});

/* Many2manytags field */

patch(Many2ManyTagsField.prototype, {
    setup() {
        super.setup();
        const relation = this.relation;
        if (isCreationRestricted(relation)) {
            this.activeActions = { ...this.activeActions, create: false, createEdit: false };
            this.quickCreate = undefined;
        }
    },
});