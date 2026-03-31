/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { Card } from "./card";
import { ChartRender } from "./ChartRender";
import { DoctorList } from "./Doctorlist";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class HospitalDashboard extends Component {
    static components = { Layout, Card, ChartRender, DoctorList };
    static template = "hospital_management.HospitalDashboard";

    setup() {
        this.action = useService("action");
        this.dashboardService = useService("hospital_dashboard_service");
        this._isFetching = false; 
        
        this.state = useState({
            total: {
                patients: 0, doctors: 0, appointments: 0, today_appointments: 0,
                total_appointments: 0, total_done_count: 0, total_payment_year: 0,
                state_json: [], trend_json: [], payment_json: [],
                available_years: []
            },
            currencySymbol: "",
            trend_period: 'all',
            selected_year: null
        });

        onWillStart(async () => {
            await this.fetchDashboardData();
        });
    }



    async fetchDashboardData() {
    if (this._isFetching) return;
    this._isFetching = true;

    try {
        const params = {
            trend_period: this.state.trend_period,
            year: this.state.selected_year
        };

        const data = await this.dashboardService.getDashboardData(params);

        if (data) {
            this.state.total = { ...data };
            this.state.currencySymbol = data.currency_symbol;
        }
    } finally {
        this._isFetching = false;
    }
}

    async onTrendFilterChange(ev) {
        this.state.trend_period = ev.target.value;
        this.state.selected_year = null;
        await this.fetchDashboardData();
    }

    openListView(model, name, domain = []) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: model,
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
        });
    }

    openTodayAppointments() {
        const today = new Date().toISOString().split('T')[0];
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: "Today's Appointments",
            res_model: 'hospital.appointment',
            views: [[false, 'list'], [false, 'form']],
            domain: [
                ["start_datetime", ">=", today + " 00:00:00"],
                ["start_datetime", "<=", today + " 23:59:59"],
                ["state", "in", ["confirm", "consult", "done"]]
            ],
        });
    }

    get appointmentChartData() {
        const data = this.state.total.state_json || [];
        return {
            labels: data.map(d => d.state),
            counts: data.map(d => d.__count || 0),
        };
    }

    get trendChartData() {
        const trend = this.state.total.trend_json || [];
        let periods = [...new Set(trend.map(d => d.label))];
        
        if (this.state.trend_period === 'all') {
            periods.sort((a, b) => parseInt(a) - parseInt(b));
        } else if (this.state.trend_period === 'this_year') {
            const monthOrder = ['January', 'February', 'March', 'April', 'May', 'June', 
                               'July', 'August', 'September', 'October', 'November', 'December'];
            periods.sort((a, b) => monthOrder.indexOf(a) - monthOrder.indexOf(b));
        } else {
            periods.sort((a, b) => {
                const aWeek = parseInt(a.match(/W(\d+)/)?.[1] || 0);
                const bWeek = parseInt(b.match(/W(\d+)/)?.[1] || 0);
                return aWeek - bWeek;
            });
        }
        
        const states = [...new Set(trend.map(d => d.state))];
        
        return {
            labels: periods,
            datasets: states.map(s => ({
                label: s,
                data: periods.map(p => {
                    const found = trend.find(d => d.label === p && d.state === s);
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
                const found = data.find(d => d.label === m);
                return found ? (found.__count || 0) : 0;
            })
        };
    }
    
    get totalAppointments() { return this.state.total.total_appointments || 0; }
    get totalDoneCount() { return this.state.total.total_done_count || 0; }
    get totalPaymentYear() { return this.state.total.total_payment_year || 0; }

   
}
registry.category("actions").add("hospital_dashboard_tag", HospitalDashboard);