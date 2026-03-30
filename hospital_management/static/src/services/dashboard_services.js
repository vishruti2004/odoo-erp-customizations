import { registry } from "@web/core/registry";

export const hospitalDashboardService = {
    dependencies: ["rpc"],
    start(env, { rpc }) { // અહીં { rpc } લખવું જરૂરી છે
        return {
            async fetchData(trend_period, selected_year) {
                return await rpc("/hospital/dashboard_data", {
                    trend_period: trend_period,
                    year: selected_year
                });
            },
        };
    },
};

registry.category("services").add("hospital_dashboard_service", hospitalDashboardService);