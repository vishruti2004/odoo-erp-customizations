/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { X2ManyField } from "@web/views/fields/x2many/x2many_field";

patch(X2ManyField.prototype, {
    get nestedKeyOptionalFieldsData() {
        return {
            ...super.nestedKeyOptionalFieldsData,
            o2mCopyPasteEnabled:
                this.props.viewMode === "list" && this.field.type === "one2many",
        };
    },
});
