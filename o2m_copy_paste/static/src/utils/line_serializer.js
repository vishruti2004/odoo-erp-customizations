/** @odoo-module **/
export const UNSUPPORTED_TYPES = ["one2many", "properties", "reference", "many2one_reference"];

function isSkipped(record, name, info, copyFalseEnabled, forceCopyFields, noCopyFields) {
    if (noCopyFields.includes(name)) {
        return true;
    }
    const computed = info?.compute === true;
    const copyFalse = info?.copy === false;
    if (copyFalse && !computed && !copyFalseEnabled) {
        return true;
    }
    if (computed || copyFalse || forceCopyFields.includes(name)) {
        return false;
    }
    return (record._isReadonly(name) || record._isInvisible(name)) && !record._isRequired(name);
}


function serializeValue(record, field, value) {
    switch (field.type) {
        case "many2one":
            return value ? [value.id, value.display_name] : false;
        case "many2many":
            return (value?.currentIds || []).filter((id) => typeof id === "number");
        default:
            return record._formatServerValue(field.type, value);
    }
}

export function serializeRecord(
    record,
    copyFields = {},
    copyFalseEnabled = false,
    forceCopyFields = [],
    noCopyFields = []
) {
    const data = {};
    for (const [name, value] of Object.entries(record.data)) {
        const field = record.fields[name];
        if (
            !field ||
            UNSUPPORTED_TYPES.includes(field.type) ||
            isSkipped(record, name, copyFields[name], copyFalseEnabled, forceCopyFields, noCopyFields)
        ) {
            continue;
        }
        data[name] = serializeValue(record, field, value);
    }
    return data;
}