/** @odoo-module **/

import { clamp } from '@web/core/utils/numbers';
import { SplitViewController } from "./split_view_controller";
import { SplitViewForm } from "./split_view_form";
import { Component, useEffect, useRef, useChildSubEnv, onMounted, onWillDestroy } from '@odoo/owl';

// Share of the container the list/kanban side may occupy while dragging.
const MIN_WIDTH_RATIO = 0.25;
const MAX_WIDTH_RATIO = 0.75;

/**
 * SplitviewContainer - Container component for the split view form panel
 * Manages the form view display and resizable separator
 */
export class SplitviewContainer extends Component {
    static template = 'split_view.SplitviewContainer';
    static components = {
        SplitViewForm,
    };

    static props = {
        context: { type: Object, optional: true },
        viewId: { type: [Number, { value: false }], optional: true },
        record: { type: Object, optional: true },
        resModel: { type: String },
        resId: { type: Number },
        resIds: { type: Array },
        onUpdate: { type: Function, optional: true },
    };

    setup() {
        super.setup();

        this.separator = useRef('separator');
        this.formviewPanel = useRef('formview-panel');
        this.formviewContainer = useRef('formview-container');

        // Inject custom SplitViewController into child environment
        useChildSubEnv({
            config: {
                ...this.env.config,
                Controller: SplitViewController,
            },
        });

        // Update form styling when resId changes
        useEffect(
            () => this._updateSplitViewForm(),
            () => [this.props.resId]
        );

        onMounted(() => this._onMounted());
        onWillDestroy(() => this._cleanup());
    }

    /**
     * Called when component is mounted
     * Adds necessary classes to parent elements for proper CSS targeting
     * Uses direct DOM queries (descendant, not direct child) for reliability
     */
    _onMounted() {
        const panelEl = this.formviewPanel.el;
        if (!panelEl) return;

        // Find elements using descendant selector (more flexible)
        // Use querySelector without > for more reliable matching
        const actionManager = document.querySelector('body.split_view_active .o_action_manager');
        const viewController = actionManager?.querySelector('.o_view_controller');
        const oContent = viewController?.querySelector('.o_content');

        // Add classes for CSS targeting (critical for split layout!)
        if (actionManager) {
            actionManager.classList.add('split_view_split');
        }
        if (viewController) {
            viewController.classList.add('split_view_viewer');
        }
        if (oContent) {
            oContent.classList.add('split_view_content');
        }
        panelEl.classList.add('split_view_form_viewer');
    }

    /**
     * Cleanup classes and any drag still in progress.
     * The separator itself is owned by Owl and removed with the component.
     */
    _cleanup() {
        // End an in-flight drag so its document listeners are released
        if (this._stopResize) {
            this._stopResize();
        }

        // Remove classes from parent elements using direct query
        const oContent = document.querySelector('.o_content.split_view_content');
        const actionManager = document.querySelector('.o_action_manager.split_view_split');
        const viewController = document.querySelector('.o_view_controller.split_view_viewer');

        if (oContent) {
            oContent.classList.remove('split_view_content');
        }
        if (actionManager) {
            actionManager.classList.remove('split_view_split');
        }
        if (viewController) {
            viewController.classList.remove('split_view_viewer');
        }

        // Reset list wrapper inline styles
        const listWrapper = document.querySelector('.split_view_list_wrapper');
        if (listWrapper) {
            listWrapper.style.width = '';
            listWrapper.style.minWidth = '';
            listWrapper.style.maxWidth = '';
        }
    }

    /**
     * The element resized by the separator: the wrapper for list views, the
     * renderer itself for kanban views.
     * @returns {HTMLElement|null}
     */
    _getResizableElement() {
        const parentEl = this.formviewPanel.el?.parentElement;
        return parentEl?.querySelector('.split_view_list_wrapper') ||
            parentEl?.querySelector('.o_kanban_renderer') ||
            null;
    }

    /**
     * Start a resize drag. The pointermove/pointerup listeners live only for
     * the duration of the drag, so nothing accumulates on document.
     * @param {PointerEvent} ev
     */
    onSeparatorPointerDown(ev) {
        const resizable = this._getResizableElement();
        const containerWidth = resizable?.parentElement?.offsetWidth;
        if (!resizable || !containerWidth) {
            return;
        }

        ev.preventDefault();

        const startX = ev.clientX;
        const startWidth = resizable.offsetWidth;
        const minWidth = containerWidth * MIN_WIDTH_RATIO;
        const maxWidth = containerWidth * MAX_WIDTH_RATIO;

        this.separator.el?.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';

        const onPointerMove = (moveEv) => {
            const newWidth = clamp(startWidth + moveEv.clientX - startX, minWidth, maxWidth);
            resizable.style.width = `${newWidth}px`;
            resizable.style.minWidth = `${newWidth}px`;
            resizable.style.maxWidth = `${newWidth}px`;
            resizable.style.flexShrink = '0';
        };

        const stopResize = () => {
            document.removeEventListener('pointermove', onPointerMove);
            document.removeEventListener('pointerup', stopResize);
            this.separator.el?.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            this._stopResize = null;
        };

        document.addEventListener('pointermove', onPointerMove);
        document.addEventListener('pointerup', stopResize);
        this._stopResize = stopResize;
    }

    /**
     * Update form view styling
     */
    _updateSplitViewForm() {
        const formView = this.formviewContainer.el?.querySelector('.o_form_view');
        if (formView) {
            // Remove extra large form view class for better fit
            formView.classList.remove('o_xxl_form_view');
        }
    }

    /**
     * Get props for the SplitViewForm component
     * Enables action menus and layout actions for smart buttons
     * @returns {Object} - Form view props
     */
    get formViewProps() {
        const resIds = this.props.resIds || [];
        return {
            context: { ...(this.props.context || {}) },
            loadActionMenus: true,  // Enable action menus (Print, Export, etc.)
            display: {
                controlPanel: { layoutActions: true },  // Enable smart buttons
            },
            viewId: this.props.viewId,
            className: 'split_view_form',
            resModel: this.props.resModel,
            resId: this.props.resId,
            resIds: resIds,
            onUpdate: this.props.onUpdate,
        };
    }
}
