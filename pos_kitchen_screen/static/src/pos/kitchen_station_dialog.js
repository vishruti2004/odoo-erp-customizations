import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class KitchenStationDialog extends Component {
    static template = "pos_kitchen_screen.KitchenStationDialog";
    static components = { Dialog };
    static props = {
        title: String,
        stations: Array,
        current: { optional: true },
        confirm: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            selected: this.props.current === undefined ? 0 : this.props.current,
        });
    }

    select(id) {
        this.state.selected = id;
    }

    onConfirm() {
        this.props.confirm(this.state.selected);
        this.props.close();
    }
}
