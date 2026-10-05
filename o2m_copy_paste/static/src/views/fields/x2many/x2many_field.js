/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

// Enables copy/paste One2many fields in list view.

patch(X2ManyField.prototype, {
    get nestedKeyOptionalFieldsData() {
        return {
            ...super.nestedKeyOptionalFieldsData,
            o2mCopyPasteEnabled:
                this.props.viewMode === "list" &&
                !this.isMany2Many &&
                this.field.type === "one2many",
        };
    },
});
