import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

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

export class KitchenChefDialog extends Component {
    static template = "pos_kitchen_screen.ChefDialog";
    static components = { Dialog };
    static props = {
        chefs: Array,
        current: { optional: true },
        login: Function,
        logout: Function,
        close: Function,
    };

    pick(chef) {
        this.props.login(chef.id);
        this.props.close();
    }

    onLogout() {
        this.props.logout();
        this.props.close();
    }
}
