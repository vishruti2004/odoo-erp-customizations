/** @odoo-module **/

export function isCompatible(clipboard, list) {
    return !!clipboard && !!list && clipboard.resModel === list.resModel;
}
