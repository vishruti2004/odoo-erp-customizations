/** @odoo-module **/

import { onMounted, onWillDestroy } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        this.o2mClipboard = useService("o2m_copy_paste");

        if (this.isO2MCopyPasteEnabled) {
            onMounted(() => this.o2mClipboard.register(this));
            onWillDestroy(() => this.o2mClipboard.unregister(this));
        }
    },

    get isO2MCopyPasteEnabled() {
        return (
            this.o2mClipboard.isEnabled() &&
            this.props.nestedKeyOptionalFieldsData?.o2mCopyPasteEnabled === true
        );
    },

    get hasSelectors() {
        return (
            super.hasSelectors ||
            (this.isO2MCopyPasteEnabled && !this.env.isSmall)
        );
    },

    get selectAll() {
        if (!this.isO2MCopyPasteEnabled) {
            return super.selectAll;
        }

        const records = this.props.list.records;

        return (
            records.length > 0 &&
            records.every((record) => record.selected)
        );
    },

    async toggleSelection() {
        if (!this.isO2MCopyPasteEnabled) {
            return super.toggleSelection(...arguments);
        }

        if (!this.canSelectRecord) {
            return;
        }

        const records = this.props.list.records;

        const select =
            !(
                records.length > 0 &&
                records.every((record) => record.selected)
            );

        for (const record of records) {
            await record.toggleSelection(select);
        }
    },

    getO2MSelectedRecords() {
        return this.props.list.records.filter(
            (record) => record.selected
        );
    },

    canO2MPaste() {
        return (
            this.isO2MCopyPasteEnabled &&
            !this.props.readonly &&
            this.props.activeActions?.create !== false
        );
    },
});