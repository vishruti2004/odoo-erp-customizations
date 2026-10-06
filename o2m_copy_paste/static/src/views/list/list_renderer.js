/** @odoo-module **/

import { onMounted, onWillDestroy, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { ListRenderer } from "@web/views/list/list_renderer";

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);

        this.o2mClipboard = useService("o2m_copy_paste");
        this.orm = useService("orm");

        this.o2mCopyPasteState = useState({
            enabled: false,
            registered: false,
        });

        onMounted(async () => {
            await this.loadO2MCopyPasteSetting();

            if (this.isO2MCopyPasteEnabled) {
                this.o2mClipboard.register(this);
                this.o2mCopyPasteState.registered = true;
            }
        });

        onWillDestroy(() => {
            if (this.o2mCopyPasteState.registered) {
                this.o2mClipboard.unregister(this);
            }
        });
    },

    async loadO2MCopyPasteSetting() {
        try {
            this.o2mCopyPasteState.enabled = await this.orm.call(
                "o2m.copy.paste",
                "get_copy_paste_enabled",
                []
            );
        } catch {
            this.o2mCopyPasteState.enabled = false;
        }
    },

    get isO2MCopyPasteEnabled() {
        return (
            this.o2mCopyPasteState.enabled &&
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