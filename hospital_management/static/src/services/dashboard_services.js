/** @odoo-module **/
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc"; 
import { memoize } from "@web/core/utils/functions";
import { reactive } from "@odoo/owl";

export const hospitalDashboardService = {
    dependencies: [],
    start(env) {
        //get data from server
        const _fetchData = (paramsString) => {
            const params = JSON.parse(paramsString);
            console.log("Calling Server for:", params);
            return rpc("/hospital/dashboard_data", params);
        };

        const cachedFetch = memoize(_fetchData);

        return reactive({
            getDashboardData(params) {
                return cachedFetch(JSON.stringify(params));
            },
        });
    },
};

registry.category("services").add("hospital_dashboard_service", hospitalDashboardService);