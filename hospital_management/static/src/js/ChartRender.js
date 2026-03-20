/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { Component, onWillStart, onMounted, useRef, onWillUnmount, useEffect } from "@odoo/owl";

export class ChartRender extends Component {
    static template = "hospital_management.ChartRender";
    static props = {
        type: { type: String, optional: true },
        label: { type: String },
        data: { type: Object },
    };

    setup() {
        this.chartRef = useRef("chartCanvas");
        this.chart = null;

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
        });

        onMounted(() => {
            this.renderChart();
        });

        useEffect(() => {
            if (this.props.data && this.props.data.labels && this.props.data.labels.length > 0) {
                this.renderChart();
            }
        }, () => [this.props.data]);

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    renderChart() {
        if (this.chart) {
            this.chart.destroy();
        }

        const canvas = this.chartRef.el;
        if (!canvas) return;

        this.chart = new Chart(canvas, {
            type: this.props.type || 'Pie',
            data: {
                labels: this.props.data.labels,
                datasets: [{
                    label: this.props.label,
                    data: this.props.data.counts,
                    backgroundColor: [
                       '#e74c3c' , '#219d9b', '#f1c40f','#574e7e' , '#d3dbe2', '#199a4e'
                    ],
                    hoverOffset: 15,
                    borderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '70%', 
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true,
                        }
                    },
                    tooltip: {
                        enabled: true,
                        callbacks: {
                            label: function(context) {
                                return ` ${context.label}: ${context.raw}`;
                            }
                        }
                    }
                }
            }
        });
    }
}