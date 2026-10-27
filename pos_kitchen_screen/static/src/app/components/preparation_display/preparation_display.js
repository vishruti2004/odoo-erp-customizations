import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { _t } from "@web/core/l10n/translation";
import { PrepDisplay } from "@pos_enterprise/app/components/preparation_display/preparation_display";

PrepDisplay.components = { ...PrepDisplay.components, Dropdown, DropdownItem };
patch(PrepDisplay.prototype, {
    setup() {
        super.setup(...arguments);
        this.kitchen = useState(this.prepDisplay.kitchen);
    },

    get kitchenRootClass() {
        return this.prepDisplay.kitchenAdvanced ? "o_kitchen_active" : "";
    },
    get kitchenChefLabel() {
        if (this.prepDisplay.kitchenRestricted && !this.kitchen.access?.chef) {
            return _t("No chef linked");
        }
        return this.kitchen.chef ? this.kitchen.chef.name : _t("All chefs");
    },
    get kitchenIsAdmin() {
        return this.prepDisplay.kitchenIsAdmin;
    },
    get showStationFilter() {
        return this.prepDisplay.kitchenAdvanced && this.prepDisplay.visibleStations.length > 1;
    },
    toggleStationFilter(stationId) {
        const list = this.kitchen.stationFilter;
        const index = list.indexOf(stationId);
        if (index >= 0) {
            list.splice(index, 1);
        } else {
            list.push(stationId);
        }
    },
    setChefFilter(value) {
        if (value === "all") {
            this.prepDisplay.logoutChef();
            return;
        }
        this.kitchen.chefFilter = value;
    },
    setPriorityFilter(value) {
        this.kitchen.priorityFilter = value;
    },
});
