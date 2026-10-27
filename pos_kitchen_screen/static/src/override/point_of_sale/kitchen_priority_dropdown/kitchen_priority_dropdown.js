import { Component } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";

export class KitchenPriorityDropdown extends Component {
    static template = "pos_kitchen_screen.KitchenPriorityDropdown";
    static components = { Dropdown, DropdownItem };
    static props = {
        order: { type: Object, optional: true },
        onSelect: Function,
        buttonClass: { type: String, optional: true },

        withPrefix: { type: Boolean, optional: true },
    };

    get priority() {
        return this.props.order?.kitchen_priority || "medium";
    }
    get options() {
        return [
            { id: "high", label: _t("High") },
            { id: "medium", label: _t("Medium") },
            { id: "low", label: _t("Low") },
        ];
    }
    get current() {
        return this.options.find((option) => option.id === this.priority);
    }
    get label() {
        if (!this.props.withPrefix) {
            return this.current.label;
        }
        return this.priority === "medium"
            ? _t("Priority")
            : _t("Priority: %s", this.current.label);
    }
    select(priority) {
        if (priority !== this.priority) {
            this.props.onSelect(priority);
        }
    }
}
