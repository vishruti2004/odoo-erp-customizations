import { Component, useRef } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class GuestAssignPopup extends Component {
    static template = "pos_restaurant_guest_queue.GuestAssignPopup";
    static components = { Dialog };

    setup() {
        this.guestSelect = useRef("guestSelect");
    }
    async assignGuest() {
        const guestId = parseInt(this.guestSelect.el.value);
        // Update guest state in backend
        await this.props.pos.data.call("pos.guest.queue", "assign_guest_to_table", [guestId, this.props.tableId]);
        const table = this.props.pos.models["restaurant.table"].get(this.props.tableId);
        this.props.close();
        if (table) {
            await this.props.pos.setTableFromUi(table);
        }
    }
}