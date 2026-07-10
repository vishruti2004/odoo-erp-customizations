/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { Many2One } from "@web/views/fields/many2one/many2one";
import { Many2ManyTagsField } from "@web/views/fields/many2many_tags/many2many_tags_field";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

function isCreationRestricted(resModel) {
    const config = session.quick_create_restriction || {};

    if (!config.enabled) return false;
    if (!resModel) return false;

    const restrictedModels = config.model_ids || [];
    const allowedGroups = config.allowed_group_ids || [];
    const currentUserGroups = config.current_user_group_ids || [];

    const modelRestricted = !restrictedModels.length || restrictedModels.includes(resModel);
    if (!modelRestricted) return false;

    if (allowedGroups.length) {
        const isAllowed = currentUserGroups.some((id) => allowedGroups.includes(id));
        return !isAllowed;
    }

    return true;
}

patch(Many2One.prototype, {
    get activeActions() {
        if (isCreationRestricted(this.props.relation)) {
            return {
                ...super.activeActions,
                create: false,
                createEdit: false,
            };
        }
        return super.activeActions;
    },

    get many2XAutocompleteProps() {
        const props = super.many2XAutocompleteProps;
        if (isCreationRestricted(this.props.relation)) {
            return { ...props, quickCreate: null };
        }
        return props;
    },
});

patch(Many2ManyTagsField.prototype, {
    setup() {
        super.setup();
        if (isCreationRestricted(this.relation)) {
            this.activeActions = {
                ...this.activeActions,
                create: false,
                createEdit: false,
            };
            this.quickCreate = undefined;
        }
    },
});

patch(SelectCreateDialog.prototype, {
    setup() {
        super.setup();
        if (isCreationRestricted(this.props.resModel)) {
            Object.assign(this.props, { noCreate: true });
        }
    },
});

patch(X2ManyField.prototype, {
    setup() {
        super.setup();
        const relation = this.props.record.fields[this.props.name]?.relation;
 
        if (isCreationRestricted(relation)) {
            this.activeActions = {
                ...this.activeActions,
                create: false,
                createEdit: false,
                link: false,
            };
        }
    },
});
