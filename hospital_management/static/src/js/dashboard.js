import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { Card } from "./card";
import { ChartRender } from "./ChartRender";
import { DoctorList } from "./Doctorlist";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class HospitalDashboard extends Component {
    static components = { Layout, Card, ChartRender, DoctorList };
    static template = "hospital_management.HospitalDashboard";

    setup() {
        this.action = useService("action");
        this.state = useState({
            total: {
                patients: 0, doctors: 0, appointments: 0, today_appointments: 0,
                total_done_count: 0,
                state_json: [], trend_json: [], payment_json: [],
                available_years: []
            },
            currencySymbol: "",
            trend_period: 'all', // Default 'all' 
            selected_year: null
        });

        onWillStart(async () => {
            await this.fetchDashboardData();
        });
    }

    async fetchDashboardData() {
        const data = await rpc("/hospital/dashboard_data", {
            trend_period: this.state.trend_period,
            year: this.state.selected_year
        });
        if (data) {
            this.state.total = data;
            this.state.currencySymbol = data.currency_symbol;
        }
    }

    async onTrendFilterChange(ev) {
        const value = ev.target.value;
        this.state.trend_period = value;
        
        if (value === 'selected_year') {
            this.state.selected_year = null;
        } else {
            this.state.selected_year = null;
        }
        
        await this.fetchDashboardData();
    }
    
    async onYearChange(ev) {
        this.state.selected_year = ev.target.value;
        await this.fetchDashboardData();
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
        
        // Get unique periods in order
        let periods = [...new Set(trend.map(d => d.label))];
        
        // Sort based on trend period type
        if (this.state.trend_period === 'all') {
            // Year sorting
            periods.sort((a, b) => parseInt(a) - parseInt(b));
        } else if (this.state.trend_period.includes('year')) {
            // Month sorting for year view
            const monthOrder = ['January', 'February', 'March', 'April', 'May', 'June', 
                               'July', 'August', 'September', 'October', 'November', 'December'];
            periods.sort((a, b) => monthOrder.indexOf(a) - monthOrder.indexOf(b));
        } else if (this.state.trend_period.includes('month')) {
            // Day sorting for month view 
            periods.sort((a, b) => parseInt(a) - parseInt(b));
        } else {
            // Week sorting
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
    
    get isYearSelected() {
        return this.state.trend_period === 'selected_year';
    }
    
    get availableYears() {
        return this.state.total.available_years || [];
    }
    
    get currentPeriodLabel() {
        if (this.state.trend_period === 'this_month') {
            return 'This Month (Days)';
        } else if (this.state.trend_period === 'previous_month') {
            return 'Previous Month (Days)';
        } else if (this.state.trend_period === 'next_month') {
            return 'Next Month (Days)';
        } else if (this.state.trend_period === 'this_year') {
            return 'This Year (Months)';
        } else if (this.state.trend_period === 'previous_year') {
            return 'Previous Year (Months)';
        } else if (this.state.trend_period === 'selected_year') {
            return 'Selected Year (Months)';
        } else {
            return 'All Time (Years)';
        }
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
}

registry.category("actions").add("hospital_dashboard_tag", HospitalDashboard);