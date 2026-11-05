/** @odoo-module **/

import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { parseServerValue } from "@web/model/relational_model/utils";
import { isCompatible } from "../utils/compatibility";
import { serializeRecord, UNSUPPORTED_TYPES } from "../utils/line_serializer";

const STORAGE_KEY = "o2m_copy_paste.clipboard";
const SETTINGS_MODEL = "o2m.copy.paste";

function toClientValue(field, value) {
    switch (field.type) {
        case "many2one":
            return value ? { id: value[0], display_name: value[1] } : false;
        case "many2many":
            return [[6, false, value || []]];
        default:
            return parseServerValue(field, value);
    }
}

function isSameValue(field, current, wanted) {
    switch (field.type) {
        case "many2one":
            return (current?.id || false) === (wanted?.id || false);
        case "many2many": {
            const currentIds = (current?.currentIds || []).filter((id) => typeof id === "number");
            const wantedIds = wanted?.[0]?.[2] || [];
            return [...currentIds].sort().join() === [...wantedIds].sort().join();
        }
        case "date":
        case "datetime":
            return (current?.toMillis?.() ?? current) === (wanted?.toMillis?.() ?? wanted);
        default:
            return (current || false) === (wanted || false);
    }
}

function buildChanges(list, values, copyFields, copyFalseEnabled) {
    const changes = {};
    for (const [name, value] of Object.entries(values)) {
        const field = list.fields[name];
        const info = copyFields[name];
        const copyFalse = info?.copy === false;
        const allowed = !copyFalse || (copyFalseEnabled && !info.compute);
        const known = name in list.activeFields || (copyFalse && copyFalseEnabled);
        if (
            !field ||
            !allowed ||
            !known ||
            UNSUPPORTED_TYPES.includes(field.type) ||
            name === list.handleField ||
            name === list.config.relationField
        ) {
            continue;
        }
        changes[name] = toClientValue(field, value);
    }
    return changes;
}

function toDefaultValue(value) {
    return Array.isArray(value) && value.length === 2 && typeof value[1] === "string"
        ? value[0]
        : value;
}

function getDefaultContext(values, forceCopyFields) {
    const context = {};
    for (const name of forceCopyFields) {
        if (values[name]) {
            context[`default_${name}`] = toDefaultValue(values[name]);
        }
    }
    return context;
}

async function applyChanges(record, list, changes, copyFields) {
    const rank = (name) => (copyFields[name]?.depends || []).filter((dep) => dep in changes).length;
    const names = Object.keys(changes).sort((a, b) => rank(a) - rank(b));
    for (let pass = 0; pass < 3; pass++) {
        let updated = false;
        for (const name of names) {
            if (pass && !(name in record.data)) {
                continue;
            }
            if (isSameValue(list.fields[name], record.data[name], changes[name])) {
                continue;
            }
            await record.update({ [name]: changes[name] });
            updated = true;
        }
        if (!updated) {
            return;
        }
    }
}

export const o2mCopyPasteService = {
    dependencies: ["notification", "orm"],

    async start(env, { notification, orm }) {
        const renderers = new Set();
        const copyFieldsCache = new Map();
        let active = null;
        let memory = null;

        const call = (method, args = [], fallback) =>
            orm.call(SETTINGS_MODEL, method, args).catch(() => fallback);
        const [enabled, copyFalseEnabled] = await Promise.all([
            call("get_copy_paste_enabled", [], false),
            call("get_copy_false_setting", [], false),
        ]);
        const notify = (message, type = "success") => notification.add(message, { type });

        function readClipboard() {
            try {
                return JSON.parse(browser.localStorage.getItem(STORAGE_KEY)) || memory;
            } catch {
                return memory;
            }
        }

        function writeClipboard(payload) {
            memory = payload;
            try {
                browser.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
            } catch {
            }
        }

        async function getCopyFields(resModel) {
            if (!copyFieldsCache.has(resModel)) {
                copyFieldsCache.set(resModel, await call("get_copy_fields", [resModel], {}));
            }
            return copyFieldsCache.get(resModel);
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
            active = liveRenderers().find((r) => r.rootRef.el.contains(target)) || active;
        }

        function pickSource() {
            const withSelection = liveRenderers().filter((r) => r.getO2MSelectedRecords().length);
            return withSelection.includes(active) ? active : withSelection[0] || null;
        }

        function pickTarget(clipboard) {
            const compatible = liveRenderers().filter((r) => isCompatible(clipboard, r.props.list));
            if (!compatible.length) {
                return { renderer: null, reason: "incompatible" };
            }
            if (compatible.includes(active)) {
                return { renderer: active };
            }
            return compatible.length === 1
                ? { renderer: compatible[0] }
                : { renderer: null, reason: "ambiguous" };
        }

        async function copy(renderer) {
            const records = renderer.getO2MSelectedRecords();
            if (!records.length) {
                return false;
            }
            const copyFields = await getCopyFields(renderer.props.list.resModel);
            writeClipboard({
                resModel: renderer.props.list.resModel,
                lines: records.map((record) =>
                    serializeRecord(
                        record,
                        copyFields,
                        copyFalseEnabled,
                        renderer.copyFields || [],
                        renderer.noCopyFields || []
                    )
                ),
            });
            const count = records.length;
            notify(count === 1 ? _t("1 line copied") : _t("%(count)s lines copied", { count }));
            return true;
        }

        async function paste(renderer, clipboard) {
            if (!renderer.canO2MPaste()) {
                notify(_t("You cannot add lines here."), "warning");
                return false;
            }
            const list = renderer.props.list;
            if (!(await list.leaveEditMode())) {
                return false;
            }
            const copyFields = await getCopyFields(list.resModel);
            const forceCopyFields = renderer.copyFields || [];
            let count = 0;
            try {
                for (const values of clipboard.lines) {
                    const context = getDefaultContext(values, forceCopyFields);
                    const record = await list.addNewRecord({
                        position: "bottom",
                        mode: "readonly",
                        ...(Object.keys(context).length && { context }),
                    });
                    const changes = buildChanges(list, values, copyFields, copyFalseEnabled);
                    for (const name of forceCopyFields) {
                        if (`default_${name}` in context) {
                            delete changes[name];
                        }
                    }
                    await applyChanges(record, list, changes, copyFields);
                    count++;
                }
            } finally {
                if (count) {
                    notify(
                        count === 1
                            ? _t("1 line pasted")
                            : _t("%(count)s lines pasted", { count })
                    );
                }
            }
            return true;
        }

        return {
            isEnabled: () => enabled,
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
            hasRenderers: () => liveRenderers().length > 0,
            notifyNoTarget(reason) {
                if (reason === "ambiguous") {
                    notify(
                        _t("Click inside the lines table where you want to paste, then press Ctrl+V."),
                        "warning"
                    );
                } else if (reason === "incompatible") {
                    notify(
                        _t("You can only paste copied lines into a One2many field of the same model."),
                        "warning"
                    );
                }
            },
        };
    },
};

registry.category("services").add("o2m_copy_paste", o2mCopyPasteService);