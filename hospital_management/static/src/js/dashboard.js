import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Counter } from "./counter";
import { Card } from "./card";
import { markup } from "@odoo/owl";
import { TodoList } from "./TodoList";

class HospitalDashboard extends Component {

    setup() {
        this.state = useState({
            sum: 0,
        });

        this.cards = [
            { title: "Patients", content: "10" },
            { title: "Doctors", content: "5" },
            { title: "Appointments", content: markup("<b>20</b>") },
        ];
    }

    incrementSum = (value) => {
        this.state.sum = this.state.sum + 1;
    };
}

HospitalDashboard.template = "hospital_dashboard_template";

HospitalDashboard.components = {
    Counter,
    Card,
    TodoList
};

registry.category("actions").add("hospital_dashboard_tag", HospitalDashboard);