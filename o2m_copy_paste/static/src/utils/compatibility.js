/** @odoo-module **/

// Returns the basic information of the O2M list.
export function getListDescriptor(list) {
    return {
        resModel: list.resModel,
        relationField: list.config?.relationField || false,
    };
}

// Checks the copied lines are compatible with the target O2M list.
export function isCompatible(clipboard, list) {
    return !!clipboard && !!list && clipboard.resModel === list.resModel;
}