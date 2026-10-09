import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { CategorySelector } from "@point_of_sale/app/components/category_selector/category_selector";

patch(CategorySelector.prototype, {
    setup() {
        super.setup(...arguments);
        this.sidebar = useState({ collapsed: false });
    },

    get categoryLayout() {
        const layout = this.pos.config.category_layout || "top_bar";
        return layout === "sidebar" && this.pos.isSmallProductScreen ? "top_bar" : layout;
    },

    get isSidebar() {
        return this.categoryLayout === "sidebar";
    },

    get layoutClass() {
        return {
            "o_pos_cat_top_bar": this.categoryLayout === "top_bar",
            "o_pos_cat_horizontal": this.categoryLayout === "horizontal",
            "o_pos_cat_sidebar": this.isSidebar,
            "o_pos_cat_right": this.isSidebar && this.pos.config.category_sidebar_position === "right",
            "o_pos_cat_collapsed": this.isSidebar && this.sidebar.collapsed,
        };
    },

    toggleSidebar() {
        this.sidebar.collapsed = !this.sidebar.collapsed;
    },

    getBreadcrumbs() {
        try {
            return this._getBreadcrumbs();
        } catch (error) {
            console.error("[pos_category_layout] breadcrumb error", error);
            return [];
        }
    },

    _getBreadcrumbs() {
        const path = [];
        let category = this.pos.selectedCategory;
        while (category) {
            path.unshift({ id: category.id, name: category.name });
            category = category.parent_id;
        }
        return path;
    },

    onBreadcrumbClick(categoryId) {
        if (categoryId === (this.pos.selectedCategory?.id || 0)) {
            return;
        }
        this.pos.setSelectedCategory(categoryId);
    },

    sortCategories(categories) {
        const alphabetical = this.pos.config.category_sort_order !== "sequence";
        return [...categories].sort((a, b) =>
            alphabetical
                ? a.name.localeCompare(b.name)
                : a.sequence - b.sequence || a.name.localeCompare(b.name)
        );
    },

    getCategoriesAndSub() {
        try {
            return this._getLayoutCategories();
        } catch (error) {
            console.error("[pos_category_layout] category list error", error);
            return super.getCategoriesAndSub(...arguments);
        }
    },

    _getLayoutCategories() {
        const selected = this.pos.selectedCategory;
        const rootIds = new Set(this.pos.rootCategories.map((c) => c.id));
        let level;
        if (!selected) {
            level = this.pos.rootCategories;
        } else if (selected.child_ids?.length) {
            level = selected.child_ids;
        } else if (selected.parent_id && !rootIds.has(selected.id)) {
            level = selected.parent_id.child_ids;
        } else {
            level = this.pos.rootCategories;
        }
        return this.sortCategories(level)
            .filter((c) => c.hasProductsToShow)
            .map((c) => ({
                ...this.getChildCategoriesInfo(c),
                isSelected: c.id === selected?.id,
            }));
    },
});
