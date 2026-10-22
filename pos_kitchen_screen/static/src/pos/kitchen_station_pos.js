import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { KitchenStationDialog } from "@pos_kitchen_screen/pos/kitchen_station_dialog";

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
    kitchenPriorityLabel(order) {
        return { high: _t("High"), medium: _t("Medium"), low: _t("Low") }[order?.kitchen_priority || "medium"];
    },
    selectKitchenPriority(order) {
        if (!order) {
            return;
        }
        this.dialog.add(KitchenStationDialog, {
            title: _t("Kitchen priority"),
            stations: [
                { id: "high", name: _t("High: prepare first") },
                { id: "medium", name: _t("Medium: normal") },
                { id: "low", name: _t("Low: can wait") },
            ],
            current: order.kitchen_priority || "medium",
            confirm: async (priority) => {
                order.kitchen_priority = priority;
                if (typeof order.id === "number") {
                    await this.data.call("pos.order", "set_kitchen_priority", [[order.id], priority]);
                }
            },
        });
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

patch(TicketScreen.prototype, {
    get kitchenPriorityAvailable() {
        return Boolean(this.pos.config?.kitchen_advanced);
    },
    onKitchenPriority(order) {
        this.pos.selectKitchenPriority(order);
    },
});
