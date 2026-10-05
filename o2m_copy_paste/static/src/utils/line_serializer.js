/** @odoo-module **/

export const ALWAYS_COPIED_FIELDS = [
    "display_type",
    "collapse_composition",
    "collapse_prices",
];
export function serializeRecord(
    record,
    copyFalseFields = {},
    copyFalseFieldsEnabled = false
) {
    const data = {};

    for (const [name, value] of Object.entries(record.data)) {
        const field = record.fields[name];

        console.log("O2M SERIALIZE CHECK:", {
            name,
            value,
            hasField: !!field,
            metadata: copyFalseFields[name],
            enabled: copyFalseFieldsEnabled,
        });

        if (!field) {
            continue;
        }

        const fieldInfo = copyFalseFields[name];
        const forced = ALWAYS_COPIED_FIELDS.includes(name);
        const isComputed = fieldInfo?.compute === true;
        const isCopyFalse = fieldInfo?.copy === false;

        if (
            isCopyFalse &&
            !isComputed &&
            !copyFalseFieldsEnabled
        ) {
            continue;
        }

        if (
            !forced &&
            !isComputed &&
            !(isCopyFalse && copyFalseFieldsEnabled) &&
            (record._isReadonly(name) ||
                record._isInvisible(name)) &&
            !record._isRequired(name)
        ) {
            continue;
        }

        switch (field.type) {
            case "many2one":
                data[name] = value
                    ? [value.id, value.display_name]
                    : false;
                break;

            case "many2many":
                data[name] = (
                    value?.currentIds || []
                ).filter(
                    (id) => typeof id === "number"
                );
                break;

            case "one2many":
            case "properties":
            case "reference":
            case "many2one_reference":
                break;

            default:
                data[name] = record._formatServerValue(
                    field.type,
                    value
                );
        }

        if (name === "qty_received_manual") {
            console.log(
                "O2M QTY_RECEIVED_MANUAL SERIALIZED:",
                data[name]
            );
        }
    }

    return data;
}