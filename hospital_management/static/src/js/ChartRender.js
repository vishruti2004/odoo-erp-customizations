/** @odoo-module **/

import { loadJS } from "@web/core/assets";
import { Component, onWillStart, onMounted, useRef, onWillUnmount, useEffect } from "@odoo/owl";

export class ChartRender extends Component {
    static template = "hospital_management.ChartRender";
    
    setup() {
        this.chartRef = useRef("chartCanvas");
        this.chart = null;

        this.stateColors = {
            'cancel': '#e74c3c',  
            'confirm': '#219d9b', 
            'consult': '#f1c40f',
            'done': '#574e7e',    
            'draft': '#d3dbe2',  
            'request': '#199a4e' 
        };

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
        });

        onMounted(() => { this.renderChart(); });
        
        useEffect(() => { this.renderChart(); }, () => [this.props.data]);
        
        onWillUnmount(() => { if (this.chart) this.chart.destroy(); });
    }

    renderChart() {
        if (!this.props.data || !this.chartRef.el) return;
        if (this.chart) this.chart.destroy();

        const type = this.props.type.toLowerCase();
        const isCircular = (type === 'pie' || type === 'doughnut');
        let datasets = [];

        // 1. Bar Chart Logic 
        if (type === 'bar') {
            datasets = (this.props.data.datasets || []).map(ds => ({
                ...ds,
                backgroundColor: this.stateColors[ds.label.toLowerCase()] || '#cccccc',
                borderWidth: 1
            }));
        } 
        // 2. Line Chart Logic 
        else if (type === 'line') {
            datasets = [{
                label: 'Total Amount',
                data: this.props.data.counts,
                borderColor: '#219d9b',
                backgroundColor: 'rgba(33, 157, 155, 0.1)',
                fill: true, tension: 0.4, borderWidth: 3
            }];
        }
        // 3. Pie/Doughnut Logic 
        else {
            const bgColors = (this.props.data.labels || []).map(l => this.stateColors[l.toLowerCase()] || '#cccccc');
            datasets = [{
                label: this.props.label || 'Status',
                data: this.props.data.counts,
                backgroundColor: bgColors,
                hoverOffset: 15
            }];
        }

        // Final Chart Object Creation
        this.chart = new Chart(this.chartRef.el, {
            type: type,
            data: { 
                labels: this.props.data.labels || [], 
                datasets: datasets 
            },
            options: {
                responsive: true, 
                maintainAspectRatio: false,
                scales: {
                    // Pie chart ma scales na hoy, etle condition muki che
                    x: { display: !isCircular, stacked: type === 'bar', grid: { display: false } },
                    y: { display: !isCircular, stacked: type === 'bar', beginAtZero: true }
                },
                plugins: { 
                    legend: { 
                        display: true, 
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 20 }
                    },
                    tooltip: {
                        enabled: true,
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) label += ': ';
                                if (context.parsed.y !== undefined) {
                                    label += context.parsed.y;
                                } else {
                                    label += context.parsed;
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    }
}