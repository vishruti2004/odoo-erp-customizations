/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { Navbar } from "@point_of_sale/app/components/navbar/navbar";
import { registry } from "@web/core/registry";

function formatArrivalTime(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    return date.toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
    }).replace(",", "");
}

// ─── Guest List Screen 
export class GuestListScreen extends Component {
    static template = "pos_restaurant_guest_queue.GuestListScreen";
    static components = {};
    static props = {};
    static storeOnOrder = false;

    setup() {
        this.pos = usePos();
        this.state = useState({
            guests: [],
            loading: true,
            currentPage: 1,
            pageSize: 10,
            searchTerm: "",
            selectedFilter: "all",
            showDropdown: false,
        });
        this.loadGuests();
    }

    async loadGuests() {
        try {
            const guests = await this.pos.data.call(
                "pos.guest.queue",
                "search_read",
                [[]],
                {
                    fields: ["name", "guest_name", "phone", "party_size", "arrival_time", "state"],
                    order: "arrival_time asc",
                }
            );
            this.state.guests = guests.map(g => ({
                ...g,
                arrival_time: formatArrivalTime(g.arrival_time),
            }));
        } catch (e) {
            console.error("Error loading guests:", e);
        } finally {
            this.state.loading = false;
        }
    }

    onSearch(ev) {
        this.state.searchTerm = ev.target.value;
        this.state.currentPage = 1;
    }

    onFilter(filter) {
        this.state.selectedFilter = filter;
        this.state.currentPage = 1;
        this.state.showDropdown = false;
    }

    getFilterLabel() {
        const map = {
            all: "All",
            waiting: "Waiting",
            notified: "Notified",
            seated: "Seated",
            cancelled: "Cancelled",
        };
        return map[this.state.selectedFilter] || "All";
    }

    get filteredGuests() {
        let guests = this.state.guests;
        if (this.state.selectedFilter !== "all") {
            guests = guests.filter(g => g.state === this.state.selectedFilter);
        }
        if (this.state.searchTerm) {
            const term = this.state.searchTerm.toLowerCase();
            guests = guests.filter(g =>
                g.guest_name?.toLowerCase().includes(term) ||
                g.name?.toLowerCase().includes(term) ||
                g.phone?.includes(term) ||
                g.party_size?.toString().includes(term)
            );
        }
        return guests;
    }

    get totalPages() {
        return Math.ceil(this.filteredGuests.length / this.state.pageSize) || 1;
    }

    get pagedGuests() {
        const start = (this.state.currentPage - 1) * this.state.pageSize;
        return this.filteredGuests.slice(start, start + this.state.pageSize);
    }

    prevPage() {
        if (this.state.currentPage > 1) this.state.currentPage--;
    }

    nextPage() {
        if (this.state.currentPage < this.totalPages) this.state.currentPage++;
    }

    getStateBadge(state) {
        const map = {
            waiting: "text-bg-warning",
            notified: "text-bg-info",
            seated: "text-bg-success",
            cancelled: "text-bg-danger",
        };
        return map[state] || "text-bg-secondary";
    }

    onNew() {
        this.pos.navigate("GuestFormScreen");
    }
}

registry.category("pos_pages").add("GuestListScreen", {
    name: "GuestListScreen",
    component: GuestListScreen,
    route: `/pos/ui/${odoo.pos_config_id}/guest-list`,
    params: {},
});

// ─── Guest Form Screen 
export class GuestFormScreen extends Component {
    static template = "pos_restaurant_guest_queue.GuestFormScreen";
    static components = {};
    static props = {};
    static storeOnOrder = false;

    setup() {
        this.pos = usePos();
        this.notification = useService("notification");

        const now = new Date();
        this.state = useState({
            form: { guest_name: "", phone: "", party_size: 1 },
            arrivalDisplay: now.toLocaleString("en-IN", {
                day: "2-digit", month: "short",
                hour: "2-digit", minute: "2-digit", hour12: true,
            }).replace(",", ""),
            error: "",
            saving: false,
        });
    }

    onBack() {
        this.pos.navigate("GuestListScreen");
    }

    validate() {
        const guestName = (this.state.form.guest_name || "").toString();
        if (!guestName.trim()) {
            this.notification.add("Guest name is required.", { type: "danger" });
            return false;
        }
        const phone = (this.state.form.phone || "").toString();
        if (!/^\d{10}$/.test(phone.trim())) {
            this.notification.add("Phone number must be exactly 10 digits.", { type: "danger" });
            return false;
        }
        if (this.state.form.party_size < 1) {
            this.notification.add("Party size must be at least 1.", { type: "danger" });
            return false;
        }
        return true;
    }

    async onSave() {
        if (!this.validate()) return;
        this.state.saving = true;
        try {
            await this.pos.data.call(
                "pos.guest.queue",
                "create",
                [[{
                    guest_name: this.state.form.guest_name.trim(),
                    phone: this.state.form.phone.trim(),
                    party_size: this.state.form.party_size,
                }]]
            );
            this.notification.add("Guest booked successfully!", { type: "success" });
            this.pos.navigate("GuestListScreen");
        } catch (e) {
            this.notification.add(e.message || "Error saving guest.", { type: "danger" });
        } finally {
            this.state.saving = false;
        }
    }
}

registry.category("pos_pages").add("GuestFormScreen", {
    name: "GuestFormScreen",
    component: GuestFormScreen,
    route: `/pos/ui/${odoo.pos_config_id}/guest-form`,
    params: {},
});

// ─── Guest List Button 
export class GuestListButton extends Component {
    static template = "pos_restaurant_guest_queue.GuestListButton";
    static components = {};

    setup() {
        this.pos = usePos();
    }

    onClick() {
        this.pos.navigate("GuestListScreen");
    }
}

patch(Navbar.prototype, {
    get isOrdersActive() {
        const current = this.pos.router.state.current;
        if (current === 'GuestListScreen' || current === 'GuestFormScreen') {
            return false;
        }
        return super.isOrdersActive;
    }
});

patch(Navbar, {
    components: {
        ...Navbar.components,
        GuestListButton,
    },
});