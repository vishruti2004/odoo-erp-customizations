/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { Card } from "./card"; 
import { ChartRender } from "./ChartRender"; 
import { rpc } from "@web/core/network/rpc"; 
import { useService } from "@web/core/utils/hooks"; 
import { Component, onWillStart, useState } from "@odoo/owl";

export class HospitalDashboard extends Component {
    static components = { Layout, Card, ChartRender }; 
    static template = "hospital_management.HospitalDashboard";

    setup() {
        this.action = useService("action");
        
        // Initial state with empty structure to avoid undefined errors
        this.state = useState({
            total: { 
                patients: 0, 
                doctors: 0, 
                appointments: 0, 
                today_appointments: 0,
                state_json: [] 
            }
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            const data = await rpc("/hospital/dashboard_data", {});
            if (data) {
                this.state.total = data;
            }
        } catch (error) {
            console.error("Dashboard RPC Error:", error);
        }
    }

    get appointmentChartData() {
    return {
        labels: this.state.total.state_json.map(d => d.state),
        counts: this.state.total.state_json.map(d => d.state_count),
    };
    }

    openListView(resModel, name, domain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: resModel,
            views: [[false, "list"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openTodayAppointments() {
        const today = new Date().toISOString().split('T')[0];
        const domain = [
            ["start_datetime", ">=", today + " 00:00:00"],
            ["start_datetime", "<=", today + " 23:59:59"],
            ["state", "in", ["confirm", "consult", "done"]]
        ];
        this.openListView("hospital.appointment", "Today's Appointments", domain);
    }
}

// Registering the action tag for Odoo Menu
registry.category("actions").add("hospital_dashboard_tag", HospitalDashboard);