import { patch } from "@web/core/utils/patch";
import { reactive, useState } from "@odoo/owl";
import { CategorySelector } from "@point_of_sale/app/components/category_selector/category_selector";

const STORAGE_KEY = "pos_category_layout.sidebar_collapsed";

function readCollapsed() {
    try {
        return window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
        return false;
    }
}

function writeCollapsed(value) {
    try {
        window.localStorage.setItem(STORAGE_KEY, value ? "1" : "0");
    } catch {
    }
}

export const categoryLayoutState = reactive({
    collapsed: readCollapsed(),
    expanded: {},
    search: "",
});

const DENSE_THRESHOLD = 12;

patch(CategorySelector.prototype, {
    setup() {
        super.setup(...arguments);
        this.layoutState = useState(categoryLayoutState);
    },

    get isCustomLayout() {
        return Boolean(this.pos.config.enable_custom_layout);
    },

    get categoryLayout() {
        const layout = this.pos.config.category_layout || "top_bar";
        return layout === "sidebar" && this.pos.isSmallProductScreen ? "top_bar" : layout;
    },

    get isSidebar() {
        return this.categoryLayout === "sidebar";
    },

    get displayStyle() {
        if (!this.isSidebar) {
            return "grid";
        }
        return this.pos.config.category_display_style === "grid" ? "grid" : "list";
    },

    get isNested() {
        return this.displayStyle === "list";
    },

    get categoryContent() {
        return this.pos.config.category_content || "image_name";
    },

    get showImage() {
        return this.categoryContent !== "name";
    },

    get isImageOnly() {
        return this.categoryContent === "image";
    },

    get showBreadcrumb() {
        return this.pos.config.category_show_breadcrumb !== false;
    },

    get showProductCount() {
        return Boolean(this.pos.config.category_show_product_count);
    },

    get showSearch() {
        return Boolean(this.pos.config.category_show_search);
    },

    get searchTerm() {
        return this.showSearch ? (this.layoutState.search || "").trim().toLowerCase() : "";
    },

    get isSearching() {
        return Boolean(this.searchTerm);
    },

    get showName() {
        return !this.isImageOnly || this.isSearching;
    },

    get showHeader() {
        return (
            this.isSidebar ||
            this.showBreadcrumb ||
            this.showSearch ||
            Boolean(this.pos.selectedCategory)
        );
    },

    get isDense() {
        return this.getLayoutItems().length > DENSE_THRESHOLD;
    },

    get layoutClass() {
        return {
            o_pos_cat_dense: this.isDense,
            [`o_pos_cat_${this.categoryLayout}`]: true,
            [`o_pos_cat_style_${this.displayStyle}`]: true,
            [`o_pos_cat_content_${this.categoryContent}`]: true,
            o_pos_cat_right: this.isSidebar && this.pos.config.category_sidebar_position === "right",
            o_pos_cat_collapsed: this.isSidebar && this.layoutState.collapsed,
        };
    },

    toggleSidebar() {
        this.layoutState.collapsed = !this.layoutState.collapsed;
        writeCollapsed(this.layoutState.collapsed);
    },

    onCategoryClick(categoryId) {
        this.layoutState.search = "";
        delete this.layoutState.expanded[categoryId];
        this.pos.setSelectedCategory(categoryId);
    },

    onSearchInput(ev) {
        this.layoutState.search = ev.target.value;
    },

    clearSearch() {
        this.layoutState.search = "";
    },

    onBackClick() {
        const parent = this.pos.selectedCategory?.parent_id;
        this.onCategoryClick(parent ? parent.id : 0);
    },

    toggleNode(item) {
        this.layoutState.expanded[item.id] = !item.expanded;
    },

    isNodeExpanded(category) {
        const manual = this.layoutState.expanded[category.id];
        return manual !== undefined ? manual : this.isAncestorOrSelected(category);
    },

    getBreadcrumbs() {
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
        this.onCategoryClick(categoryId);
    },
    sortCategories(categories) {
        const alphabetical = this.pos.config.category_sort_order === "alphabetical";
        return [...categories].sort((a, b) =>
            alphabetical
                ? a.name.localeCompare(b.name)
                : a.sequence - b.sequence || a.name.localeCompare(b.name)
        );
    },

    getCategoriesList(list, allParents, depth) {
        if (!this.isCustomLayout) {
            return super.getCategoriesList(...arguments);
        }
        const categoriesList = [...list];
        list.forEach((item) => {
            if (item.id === allParents[depth]?.id && item.child_ids?.length) {
                categoriesList.push(
                    ...this.getCategoriesList(this.sortCategories(item.child_ids), allParents, depth + 1)
                );
            }
        });
        return categoriesList;
    },

    getCategoryImage(category) {
        return category.has_image
            ? `/web/image?model=pos.category&field=image_128&id=${category.id}`
            : undefined;
    },

    getProductCount(category) {
        return category.associatedProducts.filter((product) => product.canBeDisplayed).length;
    },

    toItem(category, extra = {}) {
        return {
            ...this.getChildCategoriesInfo(category),
            imgSrc: this.showImage ? this.getCategoryImage(category) : undefined,
            initial: (category.name || "?").trim().charAt(0).toUpperCase(),
            count: this.showProductCount ? this.getProductCount(category) : 0,
            depth: 0,
            hasChildren: false,
            expanded: false,
            ...extra,
        };
    },

    getLayoutItems() {
        if (this.isSearching) {
            return this.getSearchItems();
        }
        return this.isNested ? this.getNestedItems() : this.getFlatItems();
    },

    getSearchItems() {
        const term = this.searchTerm;
        const result = [];
        const walk = (categories, trail) => {
            for (const category of this.sortCategories(categories)) {
                if (category.hasProductsToShow && (category.name || "").toLowerCase().includes(term)) {
                    result.push(this.toItem(category, { path: trail.join(" / ") }));
                }
                walk([...(category.child_ids || [])], [...trail, category.name]);
            }
        };
        walk([...this.pos.rootCategories], []);
        return result;
    },
  
    getFlatItems() {
        const selected = this.pos.selectedCategory;
        let head = null;
        let level;
        if (!selected) {
            level = [...this.pos.rootCategories];
        } else {
            const children = [...(selected.child_ids || [])].filter((c) => c.hasProductsToShow);
            if (children.length) {
                head = selected;
                level = children;
            } else if (selected.parent_id) {
                head = selected.parent_id;
                level = [...(selected.parent_id.child_ids || [])];
            } else {
                level = [...this.pos.rootCategories];
            }
        }
        const items = this.sortCategories(level)
            .filter((category) => category.hasProductsToShow)
            .map((category) => this.toItem(category));
        if (head) {
            items.unshift(this.toItem(head));
        }
        return items;
    },

    getNestedItems() {
        const selected = this.pos.selectedCategory;
        let roots = [...this.pos.rootCategories];
        if (selected) {
            const hasChildren = [...(selected.child_ids || [])].some((c) => c.hasProductsToShow);
            if (hasChildren) {
                roots = [selected];
            } else if (selected.parent_id) {
                roots = [selected.parent_id];
            }
        }
        const items = [];
        const walk = (categories, depth) => {
            for (const category of this.sortCategories(categories)) {
                if (!category.hasProductsToShow) {
                    continue;
                }
                const children = [...(category.child_ids || [])].filter((c) => c.hasProductsToShow);
                const expanded = children.length > 0 && this.isNodeExpanded(category);
                items.push(
                    this.toItem(category, { depth, hasChildren: children.length > 0, expanded })
                );
                if (expanded) {
                    walk(children, depth + 1);
                }
            }
        };
        walk(roots, 0);
        return items;
    },

    getItemClass(item) {
        if (this.isNested || this.isSearching) {
            return { o_pos_cat_current: this.pos.selectedCategory?.id === item.id };
        }
        return {
            "border-0": item.isChildren && !this.isAncestorOrSelected({ id: item.id }),
            "opacity-75 border-0": !item.isChildren && !item.isSelected,
            o_pos_cat_current: this.pos.selectedCategory?.id === item.id,
            "justify-content-center": this.ui.isSmall,
        };
    },

    getItemStyle(item) {
        return this.isNested && !this.isSearching && item.depth ? `margin-left:${item.depth * 1.25}rem` : "";
    },
});