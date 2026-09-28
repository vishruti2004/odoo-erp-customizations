/** @odoo-module **/

import { View } from '@web/views/view';
import { evaluateExpr } from '@web/core/py_js/py';
import { registry } from '@web/core/registry';
import { deepCopy, pick } from '@web/core/utils/objects';
import { extractLayoutComponents } from '@web/search/layout';
import { WithSearch } from '@web/search/with_search/with_search';
import { markRaw, toRaw } from '@odoo/owl';

const viewRegistry = registry.category('views');
const STANDARD_PROPS = [
    "resModel", "resId", "type", "arch", "fields", "relatedModels", "viewId",
    "actionMenus", "loadActionMenus", "searchViewArch", "searchViewFields",
    "searchViewId", "irFilters", "loadIrFilters", "context", "domain", "groupBy",
    "orderBy", "useSampleModel", "noContentHelp", "className", "display",
    "globalState", "activateFavorite", "dynamicFilters", "hideCustomGroupBy",
    "searchMenuTypes", "searchPanel", "searchModel",
];

/**
 * SplitViewForm - Extended View component for split view
 * Properly loads action menus and handles view configuration
 */
export class SplitViewForm extends View {
    static defaultProps = {
        type: 'form',
    };

    async loadView(props) {
        let descr = viewRegistry.get(props.type);
        const type = descr.type;
        let { viewId, searchViewId } = props;
        const views = deepCopy(props.views || this.env.config.views);

        const view = views.find((v) => v[1] === type) || [];
        if (view.length) {
            view[0] = viewId !== undefined ? viewId : view[0];
            viewId = view[0];
        } else {
            view.push(viewId || false, type);
            views.push(view);
        }

        const searchView = views.find((v) => v[1] === "search");
        if (searchView) {
            searchView[0] = searchViewId !== undefined ? searchViewId : searchView[0];
            searchViewId = searchView[0];
        } else if (searchViewId !== undefined) {
            views.push([searchViewId, "search"]);
        }

        const { context, resModel, resId, loadActionMenus, loadIrFilters } = props;
        let { arch, fields, relatedModels, searchViewArch, searchViewFields, irFilters, actionMenus } = props;

        const loadView = !arch || (!actionMenus && loadActionMenus);
        const loadSearchView = (searchViewId !== undefined && !searchViewArch) || (!irFilters && loadIrFilters);

        let viewDescription = {
            viewId,
            resModel,
            resId,
            type
        };
        let searchViewDescription;

        if (loadView || loadSearchView) {
            const result = await this.viewService.loadViews({
                context,
                resModel,
                resId,
                views
            }, {
                actionId: this.env.config.actionId,
                loadActionMenus,
                loadIrFilters
            });

            viewDescription = result.views[type];
            searchViewDescription = result.views.search;

            if (loadSearchView) {
                searchViewId = searchViewId || searchViewDescription.id;
                if (!searchViewArch) {
                    searchViewArch = searchViewDescription.arch;
                    searchViewFields = result.fields;
                }
                if (!irFilters) {
                    irFilters = searchViewDescription.irFilters;
                }
            }

            this.env.config.views = views;
            fields = fields || markRaw(result.fields);
            relatedModels = relatedModels || markRaw(result.relatedModels);
        }

        if (!arch) {
            arch = viewDescription.arch;
        }
        if (!actionMenus) {
            actionMenus = viewDescription.actionMenus;
        }

        const parser = new DOMParser();
        const xml = parser.parseFromString(arch, "text/xml");
        const rootNode = xml.documentElement;
        let subType = rootNode.getAttribute("js_class");
        const bannerRoute = rootNode.getAttribute("banner_route");
        const sample = rootNode.getAttribute("sample");

        if (subType) {
            if (viewRegistry.contains(subType)) {
                descr = viewRegistry.get(subType);
            } else {
                subType = null;
            }
        }

        Object.assign(this.env.config, {
            viewArch: rootNode,
            viewId: viewDescription.id,
            viewType: type,
            viewSubType: subType,
            bannerRoute,
            noBreadcrumbs: false,
            ...extractLayoutComponents(descr),
            ControlPanel: this.env.config.ControlPanel,
            Controller: this.env.config.Controller,
        });

        const info = {
            actionMenus,
            irFilters,
            searchViewArch,
            searchViewFields,
            searchViewId,
        };

        const viewProps = {
            info,
            arch: rootNode,
            fields,
            relatedModels,
            resModel,
            resId,
            useSampleModel: false,
            className: `${props.className} o_view_controller o_${this.env.config.viewType}_view`,
        };

        if (viewDescription.custom_view_id) {
            viewProps.info.customViewId = viewDescription.custom_view_id;
        }
        if (props.globalState) {
            viewProps.globalState = props.globalState;
        }
        if ("useSampleModel" in props) {
            viewProps.useSampleModel = props.useSampleModel;
        } else if (sample) {
            viewProps.useSampleModel = Boolean(evaluateExpr(sample));
        }

        for (const key in props) {
            if (!STANDARD_PROPS.includes(key) && key !== 'mode') {
                viewProps[key] = props[key];
            }
        }

        // Remove mode prop if exists (causes errors in FormController)
        if (viewProps.mode) {
            delete viewProps.mode;
        }

        const { noContentHelp } = props;
        if (noContentHelp) {
            viewProps.info.noContentHelp = noContentHelp;
        }

        const searchMenuTypes = props.searchMenuTypes || descr.searchMenuTypes || this.constructor.searchMenuTypes;
        viewProps.searchMenuTypes = searchMenuTypes;

        const finalProps = descr.props ? descr.props(viewProps, descr, this.env.config) : viewProps;
        this.Controller = this.env.config.Controller || descr.Controller;
        this.componentProps = finalProps;

        this.withSearchProps = {
            ...toRaw(props),
            hideCustomGroupBy: props.hideCustomGroupBy || descr.hideCustomGroupBy,
            searchMenuTypes,
            SearchModel: descr.SearchModel,
        };

        if (searchViewId !== undefined) {
            this.withSearchProps.searchViewId = searchViewId;
        }
        if (searchViewArch) {
            this.withSearchProps.searchViewArch = searchViewArch;
            this.withSearchProps.searchViewFields = searchViewFields;
        }
        if (irFilters) {
            this.withSearchProps.irFilters = irFilters;
        }
        if (descr.display) {
            const viewDisplay = deepCopy(descr.display);
            const display = {
                ...this.withSearchProps.display
            };
            for (const key in viewDisplay) {
                if (typeof display[key] === "object") {
                    Object.assign(display[key], viewDisplay[key]);
                } else if (!(key in display) || display[key]) {
                    display[key] = viewDisplay[key];
                }
            }
            this.withSearchProps.display = display;
        }

        // Clean up props not valid for WithSearch
        for (const key in this.withSearchProps) {
            if (!(key in WithSearch.props)) {
                delete this.withSearchProps[key];
            }
        }
    }

    onWillUpdateProps(nextProps) {
        const oldProps = pick(this.props, "arch", "type", "resModel", "resId");
        const newProps = pick(nextProps, "arch", "type", "resModel", "resId");

        if (JSON.stringify(oldProps) !== JSON.stringify(newProps)) {
            return this.loadView(nextProps);
        }

        const { context, domain, groupBy, orderBy } = nextProps;
        const propsToUpdate = { context, domain, groupBy, orderBy };

        // Only assign props that are valid for WithSearch component
        for (const key in propsToUpdate) {
            if (key in WithSearch.props) {
                this.withSearchProps[key] = propsToUpdate[key];
            }
        }
    }
}
