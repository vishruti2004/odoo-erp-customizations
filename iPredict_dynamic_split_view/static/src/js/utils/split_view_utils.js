/** @odoo-module **/

export function hasFormView(env) {
    const views = env.config?.views || [];

    return views.some((view) => {
        if (Array.isArray(view)) {
            return view[1] === "form";
        }

        return view?.type === "form";
    });
}