/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

console.log("Locker Kiosk JS loaded");

export class LockerKiosk extends Component {
    static template = "iPredict_locker_management.LockerKiosk";

    setup() {
        this.state = useState({
            mode: "person_search",
            personSearch: "",
            persons: [],
            selectedPerson: null,
            authentication: "",
            allocation: null,
            message: "",
            messageType: "",
            loading: false,
        });

        // Keep correct component context when called from XML event.
        this.selectPerson = this.selectPerson.bind(this);

        onMounted(() => {
            this.focusCurrentInput();
        });
    }

    focusCurrentInput() {
        setTimeout(() => {
            let selector = "";

            if (this.state.mode === "person_search") {
                selector = ".locker-person-search-input";
            }

            if (this.state.mode === "credential") {
                selector = ".locker-authentication-input";
            }

            const input = document.querySelector(selector);

            if (input) {
                input.focus();
                input.select();
            }
        }, 100);
    }

    onPersonSearchChange(ev) {
        this.state.personSearch = ev.target.value;
        this.state.message = "";
        this.state.messageType = "";
    }

    async findPerson() {
        const value = this.state.personSearch.trim();

        if (!value) {
            this.showMessage(
                "Please enter name, email or phone number.",
                "danger"
            );
            return;
        }

        this.state.loading = true;
        this.state.message = "";
        this.state.messageType = "";
        this.state.persons = [];
        this.state.selectedPerson = null;

        try {
            const result = await rpc(
                "/locker/access/find_person",
                {
                    identity: value,
                }
            );

            if (!result.success) {
                this.showMessage(
                    result.message || "No person found.",
                    "danger"
                );
                return;
            }

            this.state.persons = result.persons || [];

            if (!this.state.persons.length) {
                this.showMessage(
                    "No authorized person found.",
                    "danger"
                );
                return;
            }

            this.state.mode = "person_selection";
        } catch (error) {
            console.error(
                "Locker person search error:",
                error
            );

            this.showMessage(
                "Unable to find person. Please try again.",
                "danger"
            );
        } finally {
            this.state.loading = false;
        }
    }

    selectPerson(person) {
        if (!person) {
            console.error("No person received in selectPerson()");
            return;
        }

        console.log("Selected Person:", person);

        this.state.selectedPerson = person;
        this.state.message = "";
        this.state.messageType = "";
        this.state.authentication = "";

        this.state.mode = "credential";

        this.focusCurrentInput();
    }

    backToPersonSearch() {
        this.state.mode = "person_search";
        this.state.personSearch = "";
        this.state.persons = [];
        this.state.selectedPerson = null;
        this.state.authentication = "";
        this.state.allocation = null;
        this.state.message = "";
        this.state.messageType = "";

        this.focusCurrentInput();
    }

    onInputChange(ev) {
        this.state.authentication = ev.target.value;
        this.state.message = "";
        this.state.messageType = "";
    }

    async authenticate() {
        const value = this.state.authentication.trim();

        if (!value) {
            this.showMessage(
                "Please enter or scan your authentication credential.",
                "danger"
            );
            return;
        }

        if (!this.state.selectedPerson) {
            this.showMessage(
                "Please select a person first.",
                "danger"
            );
            return;
        }

        this.state.loading = true;
        this.state.message = "";
        this.state.messageType = "";
        this.state.allocation = null;

        try {
            const result = await rpc(
                "/locker/access/authenticate",
                {
                    identity: value,
                    partner_id: this.state.selectedPerson.partner_id,
                    allocation_id: this.state.selectedPerson.allocation_id,
                }
            );

            if (!result.success) {
                this.showMessage(
                    result.message || "Authentication failed.",
                    "danger"
                );
                return;
            }

            this.state.allocation = result.allocation;
            this.state.mode = "result";

            this.showMessage(
                "Identity verified successfully.",
                "success"
            );
        } catch (error) {
            console.error(
                "Locker authentication error:",
                error
            );

            this.showMessage(
                "Unable to authenticate. Please try again.",
                "danger"
            );
        } finally {
            this.state.loading = false;
        }
    }

    async checkIn() {
        if (!this.state.allocation) {
            return;
        }

        await this.performAccess("check_in");
    }

    async checkOut() {
        if (!this.state.allocation) {
            return;
        }

        await this.performAccess("check_out");
    }

    async performAccess(action) {
        if (!this.state.allocation) {
            return;
        }

        this.state.loading = true;

        try {
            const result = await rpc(
                "/locker/access/action",
                {
                    allocation_id: this.state.allocation.id,
                    action: action,
                    authenticated_partner_id:
                        this.state.allocation.authenticated_partner_id,
                }
            );

            if (!result.success) {
                this.showMessage(
                    result.message ||
                    "Unable to perform action.",
                    "danger"
                );
                return;
            }

            this.state.allocation = result.allocation;

            this.showMessage(
                result.message,
                "success"
            );
        } catch (error) {
            console.error(
                "Locker access action error:",
                error
            );

            this.showMessage(
                "Something went wrong. Please try again.",
                "danger"
            );
        } finally {
            this.state.loading = false;
        }
    }

    resetScreen() {
        this.state.mode = "person_search";
        this.state.personSearch = "";
        this.state.persons = [];
        this.state.selectedPerson = null;
        this.state.authentication = "";
        this.state.allocation = null;
        this.state.message = "";
        this.state.messageType = "";
        this.state.loading = false;

        this.focusCurrentInput();
    }

    showMessage(message, type) {
        this.state.message = message;
        this.state.messageType = type;
    }
}

registry.category("actions").add(
    "locker_kiosk_action",
    LockerKiosk
);