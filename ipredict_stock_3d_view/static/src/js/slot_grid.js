/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";

export class SlotGridField extends Component {
    static template = "ipredict_stock_3d_view.SlotGridField";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.ui = useState({
            selectedChildId: null,
            selectedCells: [],
            selectedRows: [],
        });
    }

    get parsed() {
        const raw = this.props.record.data.slot_grid_json;
        if (!raw || raw === "{}") return null;
        try {
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    get children() {
        const p = this.parsed;
        return p ? (p.children || []) : [];
    }

    get selectedChild() {
        return this.ui.selectedChildId;
    }

    get selectedChildName() {
        if (!this.ui.selectedChildId) return "";
        const child = this.children.find(
            child => child.id === this.ui.selectedChildId
        );
        return child ? child.complete_name : "";
    }

    onChildChange(ev) {
        const value = ev.target.value;
        this.ui.selectedChildId = value ? parseInt(value, 10) : null;
        this.ui.selectedCells = [];
        this.ui.selectedRows = [];
    }

    get assignedCount() {
        const p = this.parsed;
        return p ? (p.slots || []).length : 0;
    }

    get grid() {
        const info = this.parsed;
        if (!info) return [];

        const slotMap = new Map();

        (info.slots || []).forEach(slot => {
            slotMap.set(`${slot.level}-${slot.bin}`, {
                childId: slot.child_id,
                childName: slot.child_name,
            });
        });

        const rows = [];

        for (let level = info.levels - 1; level >= 0; level--) {
            const cells = [];

            for (let bin = 0; bin < info.bins; bin++) {
                const slot = slotMap.get(`${level}-${bin}`);
                const isMine =
                    !!slot &&
                    slot.childId === this.ui.selectedChildId;
                const isAssigned = !!slot;
                const isSelected =
                    this.isCellSelected(level, bin) ||
                    this.isRowSelected(level);

                cells.push({
                    level,
                    bin,
                    childId: slot ? slot.childId : null,
                    childName: slot ? slot.childName : null,
                    isEmpty: !slot,
                    isMine,
                    isAssigned,
                    isSelected,
                    label: `B${bin + 1}`,
                });
            }

            rows.push({
                level,
                label: `L${level + 1}`,
                cells,
                isSelected: this.isRowSelected(level),
            });
        }

        return rows;
    }

    getCellKey(level, bin) {
        return `${level}-${bin}`;
    }

    isCellSelected(level, bin) {
        return this.ui.selectedCells.includes(
            this.getCellKey(level, bin)
        );
    }

    isRowSelected(level) {
        return this.ui.selectedRows.includes(level);
    }

    get selectionText() {
        const cells = this.ui.selectedCells.length;
        const rows = this.ui.selectedRows.length;

        if (!cells && !rows) return "";

        const parts = [];

        if (rows) {
            parts.push(`${rows} row${rows > 1 ? "s" : ""}`);
        }

        if (cells) {
            parts.push(`${cells} slot${cells > 1 ? "s" : ""}`);
        }

        return parts.join(" + ");
    }

    findCell(level, bin) {
        const row = this.grid.find(row => row.level === level);
        if (!row) return null;
        return row.cells.find(cell => cell.bin === bin);
    }

    onCellClick(cell) {
        if (!this.ui.selectedChildId) {
            this.notification.add(
                "Select a child location first.",
                { type: "warning" }
            );
            return;
        }

        if (cell.isAssigned && !cell.isMine) {
            this.notification.add(
                "This slot is already assigned.",
                { type: "warning" }
            );
            return;
        }

        const key = this.getCellKey(cell.level, cell.bin);
        const index = this.ui.selectedCells.indexOf(key);

        if (index >= 0) {
            this.ui.selectedCells.splice(index, 1);
        } else {
            this.ui.selectedCells.push(key);
        }

        this.ui.selectedRows = [];
    }

    onRowClick(row) {
        if (!this.ui.selectedChildId) {
            this.notification.add(
                "Select a child location first.",
                { type: "warning" }
            );
            return;
        }

        const index = this.ui.selectedRows.indexOf(row.level);

        if (index >= 0) {
            this.ui.selectedRows.splice(index, 1);
        } else {
            this.ui.selectedRows.push(row.level);
        }

        this.ui.selectedCells = [];
    }

    getSelectedCellsForAssign() {
        const result = [];
        const used = new Set();

        for (const key of this.ui.selectedCells) {
            const [level, bin] = key.split("-").map(Number);
            const cell = this.findCell(level, bin);

            if (!cell || !cell.isEmpty) continue;

            const cellKey = this.getCellKey(level, bin);

            if (!used.has(cellKey)) {
                used.add(cellKey);
                result.push([level, bin]);
            }
        }

        for (const level of this.ui.selectedRows) {
            const row = this.grid.find(row => row.level === level);
            if (!row) continue;

            for (const cell of row.cells) {
                if (!cell.isEmpty) continue;

                const key = this.getCellKey(cell.level, cell.bin);

                if (used.has(key)) continue;

                used.add(key);
                result.push([cell.level, cell.bin]);
            }
        }

        return result;
    }

    getSelectedAssignedCells() {
        const result = [];
        const used = new Set();

        for (const key of this.ui.selectedCells) {
            const [level, bin] = key.split("-").map(Number);
            const cell = this.findCell(level, bin);

            if (!cell || !cell.isMine) continue;

            const cellKey = this.getCellKey(level, bin);

            if (!used.has(cellKey)) {
                used.add(cellKey);
                result.push([level, bin]);
            }
        }

        for (const level of this.ui.selectedRows) {
            const row = this.grid.find(row => row.level === level);
            if (!row) continue;

            for (const cell of row.cells) {
                if (!cell.isMine) continue;

                const key = this.getCellKey(cell.level, cell.bin);

                if (used.has(key)) continue;

                used.add(key);
                result.push([cell.level, cell.bin]);
            }
        }

        return result;
    }

    get canAssign() {
        return !!this.ui.selectedChildId &&
            this.getSelectedCellsForAssign().length > 0;
    }

    get canUnassign() {
        return !!this.ui.selectedChildId &&
            this.getSelectedAssignedCells().length > 0;
    }

    get assignButtonLabel() {
        const rows = this.ui.selectedRows.length;
        const slots = this.ui.selectedCells.length;

        if (rows && !slots) {
            return rows > 1 ? `Assign ${rows} Rows` : "Assign Row";
        }

        if (slots) {
            return slots > 1 ? `Assign ${slots} Slots` : "Assign Slot";
        }

        return "Assign";
    }

    get unassignButtonLabel() {
        const rows = this.ui.selectedRows.length;
        const slots = this.ui.selectedCells.length;

        if (rows && !slots) {
            return rows > 1
                ? `Unassign ${rows} Rows`
                : "Unassign Row";
        }

        if (slots) {
            return slots > 1
                ? `Unassign ${slots} Slots`
                : "Unassign Slot";
        }

        return "Unassign";
    }

    async onAssignClick() {
        const record = this.props.record;
        const resId = record.resId;

        if (!resId) {
            this.notification.add(
                "Save the rack first.",
                { type: "warning" }
            );
            return;
        }

        if (!this.ui.selectedChildId) {
            this.notification.add(
                "Select a child location first.",
                { type: "warning" }
            );
            return;
        }

        const cells = this.getSelectedCellsForAssign();

        if (!cells.length) {
            this.notification.add(
                "Select at least one available slot.",
                { type: "warning" }
            );
            return;
        }

        try {
            await this.orm.call(
                "stock.location",
                "action_bulk_slots",
                [
                    [resId],
                    cells,
                    this.ui.selectedChildId,
                    true,
                ]
            );

            await record.load();

            this.ui.selectedCells = [];
            this.ui.selectedRows = [];

            this.notification.add(
                `${cells.length} slot${cells.length > 1 ? "s" : ""} assigned successfully.`,
                { type: "success" }
            );
        } catch (e) {
            this.notification.add(
                e.message || "Could not assign slots.",
                { type: "danger" }
            );
        }
    }

    async onUnassignClick() {
        const record = this.props.record;
        const resId = record.resId;

        if (!resId) return;

        const cells = this.getSelectedAssignedCells();

        if (!cells.length) {
            this.notification.add(
                "Select an assigned slot first.",
                { type: "warning" }
            );
            return;
        }

        try {
            await this.orm.call(
                "stock.location",
                "action_bulk_slots",
                [
                    [resId],
                    cells,
                    this.ui.selectedChildId,
                    false,
                ]
            );

            await record.load();

            this.ui.selectedCells = [];
            this.ui.selectedRows = [];

            this.notification.add(
                `${cells.length} slot${cells.length > 1 ? "s" : ""} unassigned successfully.`,
                { type: "success" }
            );
        } catch (e) {
            this.notification.add(
                e.message || "Could not unassign slots.",
                { type: "danger" }
            );
        }
    }
}

registry.category("fields").add("slot_grid", {
    component: SlotGridField,
    supportedTypes: ["char"],
});