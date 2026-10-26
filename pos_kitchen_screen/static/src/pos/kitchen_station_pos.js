import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { KitchenStationDialog } from "@pos_kitchen_screen/pos/kitchen_station_dialog";
import { KitchenPriorityDropdown } from "@pos_kitchen_screen/pos/kitchen_priority_dropdown";

patch(PosStore.prototype, {
    get kitchenStations() {
        const model = this.models["pos.kitchen.station"];
        return model ? model.getAll() : [];
    },
    get kitchenOverrideAvailable() {
        return Boolean(this.config?.kitchen_advanced) && this.kitchenStations.length > 0;
    },
    selectKitchenStationForLine(line) {
        if (!line) {
            return;
        }
        this.dialog.add(KitchenStationDialog, {
            title: _t("Kitchen station"),
            stations: [
                { id: 0, name: _t("Automatic (product / category)") },
                ...this.kitchenStations
                    .map((s) => ({ id: s.id, name: s.name })),
            ],
            current: line.kitchen_station_id?.id || 0,
            confirm: (stationId) => {
                line.kitchen_station_id = stationId
                    ? this.models["pos.kitchen.station"].get(stationId)
                    : false;
            },
        });
    },
});

patch(PosStore.prototype, {
    async setKitchenPriority(order, priority) {
        if (!order || !["high", "medium", "low"].includes(priority)) {
            return;
        }
        order.kitchen_priority = priority;
        if (typeof order.id === "number") {
            await this.data.call("pos.order", "set_kitchen_priority", [[order.id], priority]);
        }
    },
});

patch(Navbar.prototype, {

    get kitchenOverrideAvailable() {
        return Boolean(this.pos?.kitchenOverrideAvailable);
    },
    onKitchenStationClick() {
        const line = this.pos.getOrder?.()?.getSelectedOrderline?.();
        this.pos.selectKitchenStationForLine(line);
    },
});

TicketScreen.components = { ...TicketScreen.components, KitchenPriorityDropdown };
patch(TicketScreen.prototype, {
    get kitchenPriorityAvailable() {
        return Boolean(this.pos.config?.kitchen_advanced);
    },
    onKitchenPriority(order, priority) {
        return this.pos.setKitchenPriority(order, priority);
    },
});

ControlButtons.components = { ...ControlButtons.components, KitchenPriorityDropdown };
patch(ControlButtons.prototype, {
    get kitchenPriorityAvailable() {
        return Boolean(this.pos.config?.kitchen_advanced);
    },
    onKitchenPriority(priority) {
        return this.pos.setKitchenPriority(this.pos.getOrder(), priority);
    },
});