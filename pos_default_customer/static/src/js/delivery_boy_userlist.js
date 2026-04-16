/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService, useChildRef } from "@web/core/utils/hooks"; 
import { Dialog } from "@web/core/dialog/dialog";
import { Input } from "@point_of_sale/app/components/inputs/input/input";
import { debounce } from "@web/core/utils/timing";
import { DeliveryBoyLine } from "@pos_default_customer/js/delivery_boy_userlist_line";

export class DeliveryBoyList extends Component {
    static components = { Dialog, Input, DeliveryBoyLine }; 
    static template = "point_of_sale.DeliveryBoyList";
    
    setup() {
        this.pos = usePos();
        this.ui = useService("ui");
        this.modalRef = useChildRef(); 
        this.state = useState({
            query: "",
            deliveryBoys: [],
            loading: false,
        });
        this._loadDeliveryBoys();
        this.onSearch = debounce(this._loadDeliveryBoys.bind(this), 200);
    }

   async _loadDeliveryBoys() {
    this.state.loading = true;
    let domain = [];
    if (this.state.query) {
        domain = [['name', 'ilike', `%${this.state.query}%`]];
    }

    try {
        const result = await this.pos.env.services.orm.searchRead(
            "res.users", 
            domain, 
            ['id', 'name', 'login']
        );
        this.state.deliveryBoys = result;
    } catch (error) {
    } finally {
        this.state.loading = false;
    }
}

    clickDeliveryBoy(deliveryBoy) {
        this.props.getPayload(deliveryBoy); 
        this.props.close(); 
    }


    updateDeliveryBoyList() {
        this._loadDeliveryBoys();
    }
}