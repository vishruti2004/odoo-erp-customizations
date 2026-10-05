/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { parseServerValue } from "@web/model/relational_model/utils";
import { getListDescriptor, isCompatible } from "../utils/compatibility";
import { serializeRecord } from "../utils/line_serializer";

const STORAGE_KEY = "o2m_copy_paste.clipboard";

export const o2mCopyPasteService = {
    dependencies: ["notification", "orm"],

    start(env, { notification, orm }) {
        const renderers = new Set();
        let active = null;
        let memory = null;

        function readClipboard() {
            try {
                const raw = browser.localStorage.getItem(STORAGE_KEY);

                if (raw) {
                    return JSON.parse(raw);
                }
            } catch {
            }
            return memory;
        }

        function writeClipboard(payload) {
            memory = payload;
            try {
                browser.localStorage.setItem(
                    STORAGE_KEY,
                    JSON.stringify(payload)
                );
            } catch {
            }
        }

        async function getCopyFalseFields(list) {
            try {
                return await orm.call(
                    "o2m.copy.paste",
                    "get_copy_fields",
                    [list.resModel]
                );
            } catch {
                return {};
            }
        }

        async function getCopyFalseSetting() {
            try {
                return await orm.call(
                    "o2m.copy.paste",
                    "get_copy_false_setting",
                    []
                );
            } catch {
                return false;
            }
        }

        function liveRenderers() {
            for (const renderer of [...renderers]) {
                if (!renderer.rootRef?.el?.isConnected) {
                    renderers.delete(renderer);
                }
            }

            if (active && !renderers.has(active)) {
                active = null;
            }

            return [...renderers];
        }

        function setActiveFromTarget(target) {
            for (const renderer of liveRenderers()) {
                if (renderer.rootRef.el.contains(target)) {
                    active = renderer;
                    return;
                }
            }
        }

        function pickSource() {
            const withSelection = liveRenderers().filter(
                (renderer) => renderer.getO2MSelectedRecords().length
            );

            if (active && withSelection.includes(active)) {
                return active;
            }

            return withSelection[0] || null;
        }

        async function copy(renderer) {
            const list = renderer.props.list;

            const records = renderer.getO2MSelectedRecords();

            if (!records.length) {
                return false;
            }

            const copyFalseFields = await getCopyFalseFields(list);

            const copyFalseFieldsEnabled =
                await getCopyFalseSetting();

            const serializedLines = records.map((record) => {
                return serializeRecord(
                    record,
                    copyFalseFields,
                    copyFalseFieldsEnabled
                );
            });

            writeClipboard({
                version: 1,
                ...getListDescriptor(list),
                copiedAt: Date.now(),
                lines: serializedLines,
            });

            notification.add(
                records.length === 1
                    ? _t("1 line copied")
                    : _t("%(count)s lines copied", {
                        count: records.length,
                    }),
                { type: "success" }
            );

            return true;
        }

        function pickTarget(clipboard) {
            const all = liveRenderers();

            if (!all.length) {
                return { renderer: null };
            }

            const compatible = all.filter((renderer) =>
                isCompatible(
                    clipboard,
                    renderer.props.list
                )
            );

            if (!compatible.length) {
                return {
                    renderer: null,
                    reason: "incompatible",
                };
            }

            if (active && compatible.includes(active)) {
                return { renderer: active };
            }

            if (compatible.length === 1) {
                return {
                    renderer: compatible[0],
                };
            }

            return {
                renderer: null,
                reason: "ambiguous",
            };
        }

        function toClientChanges(
            list,
            values,
            copyFalseFields = {},
            copyFalseFieldsEnabled = false
        ) {
            const changes = {};

            for (const [name, value] of Object.entries(values)) {
                const field = list.fields[name];

                const fieldInfo = copyFalseFields[name];

                const isCopyFalse = fieldInfo?.copy === false;

                const allowCopyFalseField =
                    isCopyFalse && copyFalseFieldsEnabled;

                if (
                    !field ||
                    (!(name in list.activeFields) &&
                        !allowCopyFalseField) ||
                    name === list.handleField ||
                    name === list.config.relationField
                ) {
                    continue;
                }

                switch (field.type) {
                    case "many2one":
                        changes[name] = value
                            ? {
                                id: value[0],
                                display_name: value[1],
                            }
                            : false;
                        break;

                    case "many2many":
                        changes[name] = [
                            [6, false, value || []],
                        ];
                        break;

                    case "one2many":
                    case "properties":
                    case "reference":
                    case "many2one_reference":
                        break;

                    default:
                        changes[name] = parseServerValue(
                            field,
                            value
                        );
                }
            }

            return changes;
        }

        function getPasteValues(
            values,
            copyFalseFields,
            copyFalseFieldsEnabled
        ) {
            const allowedValues = {};

            for (const [name, value] of Object.entries(values)) {
                const fieldInfo = copyFalseFields[name];

                if (!fieldInfo) {
                    allowedValues[name] = value;
                    continue;
                }

                const isComputed = fieldInfo.compute === true;

                const isCopyFalse = fieldInfo.copy === false;

                if (isComputed) {
                    if (!isCopyFalse) {
                        allowedValues[name] = value;
                    }

                    continue;
                }

                if (!isCopyFalse) {
                    allowedValues[name] = value;
                    continue;
                }

                if (copyFalseFieldsEnabled) {
                    allowedValues[name] = value;
                }
            }

            return allowedValues;
        }

        function getPreservedCopyFalseValues(
            list,
            values,
            copyFalseFields,
            copyFalseFieldsEnabled
        ) {
            if (!copyFalseFieldsEnabled) {
                return {};
            }

            const preservedRawValues = {};

            for (const [name, value] of Object.entries(values)) {
                const fieldInfo = copyFalseFields[name];

                if (!fieldInfo) {
                    continue;
                }

                const isComputed = fieldInfo.compute === true;

                const isCopyFalse = fieldInfo.copy === false;

                if (isComputed) {
                    continue;
                }

                if (isCopyFalse) {
                    preservedRawValues[name] = value;
                }
            }

            return toClientChanges(
                list,
                preservedRawValues,
                copyFalseFields,
                copyFalseFieldsEnabled
            );
        }

        async function paste(renderer, clipboard) {
            const list = renderer.props.list;

            if (!renderer.canO2MPaste()) {
                notification.add(
                    _t("You cannot add lines here."),
                    { type: "warning" }
                );

                return false;
            }

            const left = await list.leaveEditMode();

            if (!left) {
                return false;
            }

            const copyFalseFields =
                await getCopyFalseFields(list);

            const copyFalseFieldsEnabled =
                await getCopyFalseSetting();

            let done = 0;

            try {
                for (const values of clipboard.lines) {
                    const params = {
                        position: "bottom",
                        mode: "readonly",
                    };

                    if (values.display_type) {
                        params.context = {
                            default_display_type:
                                values.display_type,
                        };
                    }

                    const record =
                        await list.addNewRecord(params);

                    const pasteValues =
                        getPasteValues(
                            values,
                            copyFalseFields,
                            copyFalseFieldsEnabled
                        );

                    const changes =
                        toClientChanges(
                            list,
                            pasteValues,
                            copyFalseFields,
                            copyFalseFieldsEnabled
                        );

                    if (values.display_type) {
                        delete changes.display_type;
                    }

                    if (Object.keys(changes).length) {
                        await record.update(changes);
                    }

                    const preservedChanges =
                        getPreservedCopyFalseValues(
                            list,
                            values,
                            copyFalseFields,
                            copyFalseFieldsEnabled
                        );

                    if (
                        Object.keys(preservedChanges).length
                    ) {
                        await record.update(
                            preservedChanges
                        );
                    }

                    done++;
                }
            } finally {
                if (done) {
                    notification.add(
                        done === 1
                            ? _t("1 line pasted")
                            : _t(
                                "%(count)s lines pasted",
                                { count: done }
                            ),
                        { type: "success" }
                    );
                }
            }

            return true;
        }

        return {
            register(renderer) {
                renderers.add(renderer);
            },

            unregister(renderer) {
                renderers.delete(renderer);

                if (active === renderer) {
                    active = null;
                }
            },

            setActiveFromTarget,
            pickSource,
            pickTarget,
            copy,
            paste,
            readClipboard,
            hasRenderers: () =>
                liveRenderers().length > 0,

            clear() {
                memory = null;

                try {
                    browser.localStorage.removeItem(
                        STORAGE_KEY
                    );
                } catch {
                }
            },

            notifyNoTarget(reason) {
                if (reason === "ambiguous") {
                    notification.add(
                        _t(
                            "Click inside the lines table where you want to paste, then press Ctrl+V."
                        ),
                        { type: "warning" }
                    );
                } else if (reason === "incompatible") {
                    notification.add(
                        _t(
                            "The copied lines cannot be pasted in this list (different line type)."
                        ),
                        { type: "warning" }
                    );
                }
            },
        };
    },
};

registry.category("services").add("o2m_copy_paste",o2mCopyPasteService);