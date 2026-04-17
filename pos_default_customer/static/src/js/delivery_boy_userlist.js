/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { Dialog } from "@web/core/dialog/dialog";

export class DeliveryBoyList extends Component {
    static components = { Dialog };
    static template = "point_of_sale.DeliveryBoyList";

    setup() {
        super.setup(...arguments);
        this.pos = usePos();
        this.state = useState({ query: "", deliveryBoys: [] });
        this._loadDeliveryBoys();
    }

    async _loadDeliveryBoys() {
        const result = await this.pos.env.services.orm.searchRead("res.users", [], ['id', 'name', 'login']);
        console.log("=== Delivery Boys List:", result);
        this.state.deliveryBoys = result;
    }

    clickDeliveryBoy(boy) {
        console.log("LOG 2: Clicked on:", boy.name);
        
        if (this.props.onSelect) {
            console.log("LOG 3: Sending data back...");
            this.props.onSelect(boy);
        }
        
        this.props.close();
    }
}