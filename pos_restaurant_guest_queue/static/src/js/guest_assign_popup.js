import { Component, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class GuestAssignPopup extends Component {
    static template = "pos_restaurant_guest_queue.GuestAssignPopup";
    static components = { Dialog };

    setup() {
        this.tableSelect = useRef("tableSelect");
    }

    handleSelection(ev) {
        if (ev.target.tagName === 'OPTION') {
            ev.preventDefault();
            ev.target.selected = !ev.target.selected;
        }
    }

    get isCombination() {
        return this.props.tableType === "combination";
    }

    get selectedTableIds() {
        if (!this.tableSelect.el) return [];
        return Array.from(this.tableSelect.el.selectedOptions)
            .map(opt => parseInt(opt.value));
    }

    async assignGuest() {
        const tableIds = this.selectedTableIds;
        const guest = this.props.bestGuest;

        if (!tableIds.length) {
            this.props.pos.env.services.notification.add(
                "Please select at least one table!",
                { type: "danger" }
            );
            return;
        }

        const selectedTables = tableIds.map(id =>
            this.props.pos.models["restaurant.table"].get(id)
        ).filter(Boolean);

        const totalSeats = selectedTables.reduce((sum, t) => sum + t.seats, 0);

        if (totalSeats < guest.party_size) {
            this.props.pos.env.services.notification.add(
                `Not enough seats! Selected: ${totalSeats}, Required: ${guest.party_size}`,
                { type: "danger" }
            );
            return;
        }

        // get partner id
        const partnerId = await this.props.pos.data.call(
            "pos.guest.queue",
            "assign_guest_to_table",
            [guest.id, tableIds]
        );

        this.props.close();

        for (const tableId of tableIds) {
            const table = this.props.pos.models["restaurant.table"].get(tableId);
            if (table) {
                await this.props.pos.setTableFromUi(table);
            }
        }

        // set name in customer box
        setTimeout(async () => {
            if (!partnerId) return;

            // fetch partner
            let partner = this.props.pos.models["res.partner"].get(partnerId);
            console.log("=== PARTNER FROM MODELS ===", partner);

            if (!partner) {
                await this.props.pos.data.read(
                    "res.partner",
                    [partnerId],
                    ["id", "name", "phone"]
                );
                partner = this.props.pos.models["res.partner"].get(partnerId);
                console.log("=== PARTNER AFTER READ ===", partner);
            }

            if (!partner) {
                console.log("=== PARTNER NOT FOUND ===");
                return;
            }

            // partner name set on selected tables
            for (const tableId of tableIds) {
                const table = this.props.pos.models["restaurant.table"].get(tableId);
                if (!table) continue;

                const orders = this.props.pos.getTableOrders(tableId);
                const activeOrder = orders.find(o => !o.finalized);
                console.log(`=== TABLE ${table.table_number} ORDER ===`, activeOrder);

                if (activeOrder) {
                    activeOrder.setPartner(partner);
                    this.props.pos.addPendingOrder([activeOrder.id]);
                    console.log(`=== TABLE ${table.table_number} PARTNER SET ===`, partner.name);
                }
            }
        }, 1000);
    }
}