import { patch } from "@web/core/utils/patch";
import { reactive, useEffect, useRef, useState } from "@odoo/owl";
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
    page: 0,
    popup: false,
    popupSearch: "",
    popupStyle: "",
    popupPage: 0,
});

const DENSE_THRESHOLD = 12;

patch(CategorySelector.prototype, {
    setup() {
        super.setup(...arguments);
        this.layoutState = useState(categoryLayoutState);
        this.popupInput = useRef("popupSearch");
        useEffect(
            (open) => {
                if (open) {
                    this.popupInput.el?.focus();
                }
            },
            () => [this.layoutState.popup]
        );
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

    get isPopupLayout() {
        return this.categoryLayout === "popup";
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

    get cardStyle() {
        if (this.isNested || this.isSearching) {
            return "classic";
        }
        return this.pos.config.category_card_style === "cover" ? "cover" : "classic";
    },

    get showImage() {
        return this.cardStyle === "cover" || this.categoryContent !== "name";
    },

    get isImageOnly() {
        return this.cardStyle === "classic" && this.categoryContent === "image";
    },

    get showBreadcrumb() {
        return this.isPopupLayout || this.pos.config.category_show_breadcrumb !== false;
    },

    get showProductCount() {
        return Boolean(this.pos.config.category_show_product_count);
    },

    get isCarousel() {
        return !this.isSidebar && !this.isPopupLayout && Boolean(this.pos.config.category_carousel);
    },

    get isHorizontalScroll() {
        return (
            !this.isSidebar &&
            !this.isPopupLayout &&
            !this.isCarousel &&
            this.pos.config.category_scroll_direction === "horizontal"
        );
    },

    onListWheel(ev) {
        const el = ev.currentTarget;
        if (!el.closest(".o_pos_cat_hscroll")) {
            return;
        }
        if (Math.abs(ev.deltaY) > Math.abs(ev.deltaX) && el.scrollWidth > el.clientWidth) {
            el.scrollLeft += ev.deltaY;
            ev.preventDefault();
        }
    },

    get visibleRows() {
        return Math.min(Math.max(parseInt(this.pos.config.category_rows) || 3, 1), 8);
    },

    getGridColumns(paginated) {
        let columns = Math.min(Math.max(parseInt(this.pos.config.category_grid_columns) || 0, 0), 12);
        if (!columns && paginated) {
            columns = 6;
        }
        return this.ui.isSmall && columns ? Math.min(columns, 3) : columns;
    },

    get gridColumns() {
        return this.getGridColumns(this.isCarousel);
    },

    get imagePosition() {
        const position = this.pos.config.category_image_position;
        // search results always use the compact "image left" card
        if (
            this.isSearching ||
            this.cardStyle !== "classic" ||
            !["top", "bottom", "left", "right"].includes(position)
        ) {
            return "left";
        }
        return position;
    },

    get layoutStyle() {
        return this.isSidebar || this.isPopupLayout ? "" : `--cat-cols:${this.gridColumns || 1};--cat-rows:${this.visibleRows}`;
    },

    paginate(all, columns, paginated, currentPage) {
        if (!paginated) {
            return { items: all, pages: 1, page: 0, total: all.length };
        }
        const size = Math.max(columns, 1) * this.visibleRows;
        const pages = Math.max(1, Math.ceil(all.length / size));
        const page = Math.min(currentPage, pages - 1);
        return { items: all.slice(page * size, (page + 1) * size), pages, page, total: all.length };
    },

    getPaging() {
        if (this.isPopupLayout) {
            return { items: [], pages: 1, page: 0, total: 0 };
        }
        return this.paginate(
            this.getLayoutItems(),
            this.gridColumns,
            this.isCarousel,
            this.layoutState.page
        );
    },

    changePage(delta) {
        const { pages, page } = this.getPaging();
        this.layoutState.page = Math.min(Math.max(page + delta, 0), pages - 1);
    },

    onTouchStart(ev) {
        this.touchStartX = ev.changedTouches?.[0]?.clientX ?? null;
    },

    onTouchEnd(ev, inPopup = false) {
        const paginated = inPopup ? this.popupPaginated : this.isCarousel;
        if (!paginated || this.touchStartX == null) {
            return;
        }
        const dx = (ev.changedTouches?.[0]?.clientX ?? this.touchStartX) - this.touchStartX;
        this.touchStartX = null;
        if (Math.abs(dx) > 40) {
            if (inPopup) {
                this.changePopupPage(dx < 0 ? 1 : -1);
            } else {
                this.changePage(dx < 0 ? 1 : -1);
            }
        }
    },

    get showSearch() {
        return Boolean(this.pos.config.category_show_search) && !this.isPopupLayout;
    },

    get searchTerm() {
        return this.showSearch ? (this.layoutState.search || "").trim().toLowerCase() : "";
    },

    get isSearching() {
        return Boolean(this.searchTerm);
    },

    get showName() {
        // image-only mode still needs the name while searching (results come from every level)
        return !this.isImageOnly || this.isSearching;
    },

    get showHeader() {
        return (
            this.isSidebar ||
            this.isPopupLayout ||
            this.showBreadcrumb ||
            this.showSearch ||
            this.isCarousel ||
            this.showAllPopup ||
            Boolean(this.pos.selectedCategory)
        );
    },

    get isDense() {
        return !this.isPopupLayout && this.getLayoutItems().length > DENSE_THRESHOLD;
    },

    get layoutClass() {
        return {
            o_pos_cat_dense: this.isDense,
            o_pos_cat_searching: this.isSearching,
            o_pos_cat_carousel: this.isCarousel,
            o_pos_cat_hscroll: this.isHorizontalScroll,
            o_pos_cat_fixed_cols: !this.isSidebar && this.gridColumns > 0,
            [`o_pos_cat_card_${this.cardStyle}`]: true,
            [`o_pos_cat_imgpos_${this.imagePosition}`]: true,
            [`o_pos_cat_${this.isPopupLayout ? "popuplayout" : this.categoryLayout}`]: true,
            [`o_pos_cat_style_${this.displayStyle}`]: true,
            [`o_pos_cat_content_${this.categoryContent}`]: true,
            o_pos_cat_right: this.isSidebar && this.pos.config.category_sidebar_position === "right",
            o_pos_cat_collapsed: this.isSidebar && this.layoutState.collapsed,
        };
    },

    // navigation
    toggleSidebar() {
        this.layoutState.collapsed = !this.layoutState.collapsed;
        writeCollapsed(this.layoutState.collapsed);
    },

    onCategoryClick(categoryId) {
        this.layoutState.search = "";
        this.layoutState.page = 0;
        delete this.layoutState.expanded[categoryId];
        this.pos.setSelectedCategory(categoryId);
    },

    onSearchInput(ev) {
        this.layoutState.search = ev.target.value;
        this.layoutState.page = 0;
    },

    clearSearch() {
        this.layoutState.search = "";
        this.layoutState.page = 0;
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
            hasChildren: [...(category.child_ids || [])].some((c) => c.hasProductsToShow),
            hasParent: Boolean(category.parent_id),
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

    // categories popup
    get showAllPopup() {
        return Boolean(this.pos.config.category_show_all_popup);
    },

    get hasPopupButton() {
        return this.isPopupLayout || this.showAllPopup;
    },

    togglePopup(ev) {
        if (this.layoutState.popup) {
            this.closePopup();
            return;
        }
        const button = ev.currentTarget;
        const rect = button.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const root = button.closest(".o_pos_cat");
        if (this.isSidebar || !root) {
            const width = Math.min(viewportWidth - 16, 720);
            const alignLeft = rect.left + rect.width / 2 < viewportWidth / 2;
            const left = Math.max(
                8,
                Math.min(alignLeft ? rect.left : rect.right - width, viewportWidth - width - 8)
            );
            const top = rect.bottom + 8;
            const maxHeight = Math.max(viewportHeight - top - 12, 200);
            this.layoutState.popupStyle = `top:${top}px;left:${left}px;width:${width}px;max-height:${maxHeight}px`;
        } else {
            const rootRect = root.getBoundingClientRect();
            const left = Math.max(8, rootRect.left + 8);
            const width = Math.max(Math.min(rootRect.width - 16, viewportWidth - left - 8), 280);
            const top = rootRect.bottom + 2;
            const maxHeight = Math.max(viewportHeight - top - 12, 200);
            this.layoutState.popupStyle = `top:${top}px;left:${left}px;width:${width}px;max-height:${maxHeight}px`;
        }
        this.layoutState.popupSearch = "";
        this.layoutState.popupPage = 0;
        this.layoutState.popup = true;
    },

    closePopup() {
        this.layoutState.popup = false;
    },

    onPopupSearch(ev) {
        this.layoutState.popupSearch = ev.target.value;
        this.layoutState.popupPage = 0;
    },

    get popupPaginated() {
        return Boolean(this.pos.config.category_carousel);
    },

    get popupColumns() {
        return this.getGridColumns(this.popupPaginated);
    },

    getPopupPaging() {
        return this.paginate(
            this.getPopupItems(),
            this.popupColumns,
            this.popupPaginated,
            this.layoutState.popupPage
        );
    },

    changePopupPage(delta) {
        const { pages, page } = this.getPopupPaging();
        this.layoutState.popupPage = Math.min(Math.max(page + delta, 0), pages - 1);
    },

    get popupLayoutStyle() {
        return `--cat-cols:${this.popupColumns || 1};--cat-rows:${this.visibleRows}`;
    },

    getPopupLayoutClass(count) {
        return {
            o_pos_cat_dense: count > DENSE_THRESHOLD,
            o_pos_cat_carousel: this.popupPaginated,
            o_pos_cat_hscroll:
                !this.popupPaginated && this.pos.config.category_scroll_direction === "horizontal",
            o_pos_cat_fixed_cols: this.popupColumns > 0,
            [`o_pos_cat_card_${this.cardStyle}`]: true,
            [`o_pos_cat_imgpos_${this.imagePosition}`]: true,
            o_pos_cat_top_bar: true,
            o_pos_cat_style_grid: true,
            [`o_pos_cat_content_${this.categoryContent}`]: true,
        };
    },

    onPopupKeydown(ev) {
        if (ev.key === "Escape") {
            this.closePopup();
        }
    },

    onPopupPick(categoryId) {
        this.layoutState.popup = false;
        this.onCategoryClick(categoryId);
    },

    getPopupItems() {
        const term = (this.layoutState.popupSearch || "").trim().toLowerCase();
        const items = this.isNested ? this.getNestedItems() : this.getFlatItems();
        return term ? items.filter((item) => (item.name || "").toLowerCase().includes(term)) : items;
    },

    getSearchItems(term = this.searchTerm) {
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

    getColorClass(item) {
        if (!item.color) {
            return {};
        }
        const colorClass = { [`o_colorlist_item_color_${item.color}`]: true };
        const inHierarchy = item.hasChildren || item.hasParent;
        return this.pos.config.category_use_color && inHierarchy ? colorClass : {};
    },

    getItemClass(item, forceGrid = false) {
        const color = this.getColorClass(item);
        if (!forceGrid && (this.isNested || this.isSearching)) {
            return {
                ...color,
                o_pos_cat_current: this.pos.selectedCategory?.id === item.id,
                o_pos_cat_has_path: Boolean(item.path),
            };
        }
        return {
            ...color,
            "border-0": item.isChildren && !this.isAncestorOrSelected({ id: item.id }),
            "opacity-75 border-0": !item.isChildren && !item.isSelected,
            o_pos_cat_current: this.pos.selectedCategory?.id === item.id,
            "justify-content-center": this.ui.isSmall,
        };
    },

    getItemStyle(item) {
        if (this.isNested && !this.isSearching && item.depth) {
            const indent = item.depth * 1.25;
            return `margin-left:${indent}rem;width:calc(100% - ${indent}rem)`;
        }
        return "";
    },
});