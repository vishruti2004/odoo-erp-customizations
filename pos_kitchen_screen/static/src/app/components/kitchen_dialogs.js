import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";

export const REPREP_REASONS = [
    { id: "wrong_item", label: _t("Wrong item prepared") },
    { id: "cooking", label: _t("Not cooked properly") },
    { id: "temperature", label: _t("Food is cold / wrong temperature") },
    { id: "quality", label: _t("Poor quality or presentation") },
    { id: "complaint", label: _t("Customer complaint") },
    { id: "other", label: _t("Other") },
];

export class KitchenSelectDialog extends Component {
    static template = "pos_kitchen_screen.SelectDialog";
    static components = { Dialog };
    static props = {
        title: String,
        options: Array,
        current: { optional: true },
        withReason: { type: Boolean, optional: true },
        confirm: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            selected: this.props.current === undefined ? null : this.props.current,
            reason: "",
            busy: false,
        });
    }

    select(id) {
        this.state.selected = id;
    }

    async onConfirm() {
        if (this.state.selected === null || this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.props.confirm(this.state.selected, this.state.reason.trim());
        } finally {
            this.props.close();
        }
    }
}

export class KitchenInfoDialog extends Component {
    static template = "pos_kitchen_screen.InfoDialog";
    static components = { Dialog };
    static props = {
        title: String,
        intro: { type: String, optional: true },
        rows: Array,
        summary: { type: String, optional: true },
        confirmLabel: { type: String, optional: true },
        confirmClass: { type: String, optional: true },
        confirm: { type: Function, optional: true },
        close: Function,
    };

    async onConfirm() {
        try {
            await this.props.confirm();
        } finally {
            this.props.close();
        }
    }
}

export class KitchenReprepareDialog extends Component {
    static template = "pos_kitchen_screen.ReprepareDialog";
    static components = { Dialog };
    static props = {
        title: String,
        confirm: Function,
        close: Function,
    };

    setup() {
        this.reasons = REPREP_REASONS;
        this.state = useState({ reason: null, other: "", busy: false });
    }

    get canConfirm() {
        if (!this.state.reason || this.state.busy) {
            return false;
        }
        return this.state.reason !== "other" || Boolean(this.state.other.trim());
    }

    async onConfirm() {
        if (!this.canConfirm) {
            return;
        }
        this.state.busy = true;
        try {
            await this.props.confirm(
                this.state.reason,
                this.state.reason === "other" ? this.state.other.trim() : false
            );
        } finally {
            this.props.close();
        }
    }
}
