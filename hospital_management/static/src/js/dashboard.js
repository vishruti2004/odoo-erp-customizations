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
        this.state = useState({
            total: { 
                patients: 0, doctors: 0, appointments: 0, today_appointments: 0,
                total_done_count: 0, 
                state_json: [], trend_json: [], payment_json: [] 
            }
        });

        onWillStart(async () => {
            const data = await rpc("/hospital/dashboard_data", {});
            if (data) {
                this.state.total = data;
            }
        });
    }

    get appointmentChartData() {
        const data = this.state.total.state_json || [];
        return {
            labels: data.map(d => d.state || 'Draft'),
            counts: data.map(d => d.__count || d.state_count || 0),
        };
    }

    get trendChartData() {
        const trend = this.state.total.trend_json || [];
        const weeks = [...new Set(trend.map(d => d['start_datetime:week']))];
        const states = [...new Set(trend.map(d => d.state))];
        return {
            labels: weeks,
            datasets: states.map(s => ({
                label: s,
                data: weeks.map(w => {
                    const found = trend.find(d => d['start_datetime:week'] === w && d.state === s);
                    return found ? (found.__count || 0) : 0;
                })
            }))
        };
    }

    get paymentLineChartData() {
        const data = this.state.total.payment_json || [];
        const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        
        return {
            labels: months,
            counts: months.map((m) => {
                const found = data.find(d => d['start_datetime:month'] === m);
                return found ? (found.__count || 0) : 0;
            })
        };
    }

    openTodayAppointments() {
        const today = new Date().toISOString().split('T')[0];
        const domain = [
            ["start_datetime", ">=", today + " 00:00:00"],
            ["start_datetime", "<=", today + " 23:59:59"],
            ["state", "in", ["confirm", "consult", "done"]]
        ];
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: "Today's Appointments",
            res_model: 'hospital.appointment',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
        });
    }
}

registry.category("actions").add("hospital_dashboard_tag", HospitalDashboard);