/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";
import { Component, onWillStart, useState } from "@odoo/owl";

export class DoctorList extends Component {
    static template = "hospital_management.DoctorList";

    setup() {
        this.state = useState({
            isMonthWise: true,
            doctors: [],
            loading: true,
        });

        onWillStart(async () => {
            await this.fetchDoctorData();
        });
    }

    async fetchDoctorData() {
        this.state.loading = true;
        // Logic: On = month, Off = year
        const period = this.state.isMonthWise ? 'month' : 'year';
        
        try {
            const data = await rpc("/hospital/dashboard_data", { period: period });
            this.state.doctors = data.top_doctors || [];
        } catch (error) {
            console.error("RPC Error:", error);
        } finally {
            this.state.loading = false;
        }
    }

    async onTogglePeriod() {
        this.state.isMonthWise = !this.state.isMonthWise;
        await this.fetchDoctorData();
    }
}