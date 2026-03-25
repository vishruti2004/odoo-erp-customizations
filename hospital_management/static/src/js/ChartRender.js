import { loadJS } from "@web/core/assets";
import { Component, onWillStart, onMounted, useRef, onWillUnmount, useEffect } from "@odoo/owl";

export class ChartRender extends Component {
    static template = "hospital_management.ChartRender";
    
    setup() {
        this.chartRef = useRef("chartCanvas");
        this.chart = null;

        this.stateColors = {
            'Cancelled': '#e74c3c',  
            'Confirmed': '#219d9b',
            'In Consultation': '#f1c40f',
            'Done': '#574e7e',    
            'Draft': '#d3dbe2',  
            'Requested': '#199a4e'
        };

        onWillStart(async () => {
            await loadJS("https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js");
        });

        onMounted(() => { this.renderChart(); });
        useEffect(() => { this.renderChart(); }, () => [this.props.data]);
        onWillUnmount(() => { if (this.chart) this.chart.destroy(); });
    }

    getWeekNumber(d) {
        d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
        d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
        var yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
        var weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
        return weekNo;
    }
    
    getMonthRange(date) {
        const firstDay = new Date(date.getFullYear(), date.getMonth(), 1);
        const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0);
        return { firstDay, lastDay };
    }
    
    getWeekRange(date) {
        const start = new Date(date);
        start.setDate(date.getDate() - date.getDay() + (date.getDay() === 0 ? -6 : 1));
        const end = new Date(start);
        end.setDate(start.getDate() + 6);
        return { start, end };
    }

    renderChart() {
        if (!this.props.data || !this.chartRef.el) return;
        if (this.chart) this.chart.destroy();

        const self = this;
        const type = this.props.type.toLowerCase();
        const isCircular = (type === 'pie' || type === 'doughnut');
        let datasets = [];

        if (type === 'bar') {
            datasets = (this.props.data.datasets || []).map(ds => ({
                ...ds,
                backgroundColor: this.stateColors[ds.label] || '#cccccc',
                borderWidth: 1,
                borderRadius: 4
            }));
        }
        else if (type === 'line') {
            datasets = [{
                label: 'Total Amount',
                data: this.props.data.counts,
                borderColor: '#219d9b',
                backgroundColor: 'rgba(33, 157, 155, 0.1)',
                fill: true, 
                tension: 0.4, 
                borderWidth: 3,
                pointRadius: 4,
                pointBackgroundColor: '#219d9b'
            }];
        }
        else {
            const bgColors = (this.props.data.labels || []).map(l => this.stateColors[l] || '#cccccc');
            datasets = [{
                data: this.props.data.counts,
                backgroundColor: bgColors,
                hoverOffset: 15,
                borderWidth: 0
            }];
        }

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
                    x: {
                        display: !isCircular,
                        stacked: type === 'bar',
                        grid: { display: false },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45,
                            callback: function(val, index) {
                                const label = this.getLabelForValue(val);
                                
                                if (label && label.includes('W') && label.match(/W\d+/)) {
                                    return label;
                                }
                                
                                if (label && label.includes(' ') && !label.includes('-')) {
                                    const parts = label.split(' ');
                                    if (parts.length === 2 && !isNaN(parts[1])) {
                                        return parts[0]; 
                                    }
                                }
                                
                                // Year format
                                if (label && !isNaN(label) && label.length === 4) {
                                    return label;
                                }
                                
                                return label;
                            }
                        }
                    },
                    y: { 
                        display: !isCircular, 
                        stacked: type === 'bar', 
                        beginAtZero: true,
                        grid: {
                            color: '#e9ecef'
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: type !== 'line',
                        position: 'bottom',
                        labels: { 
                            usePointStyle: true, 
                            padding: 20,
                            boxWidth: 12,
                            font: {
                                size: 11
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                const label = context[0].label;
                                
                                // Handle week format 
                                if (label && label.includes('W')) {
                                    const match = label.match(/W(\d+)\s(\d{4})/);
                                    if (match) {
                                        const weekNum = parseInt(match[1]);
                                        const year = parseInt(match[2]);
                                        const date = new Date(year, 0, 1 + (weekNum - 1) * 7);
                                        const start = new Date(date);
                                        start.setDate(date.getDate() - date.getDay() + (date.getDay() === 0 ? -6 : 1));
                                        const end = new Date(start);
                                        end.setDate(start.getDate() + 6);
                                        
                                        const options = { day: '2-digit', month: 'short' };
                                        return `${start.toLocaleDateString('en-GB', options)} - ${end.toLocaleDateString('en-GB', options)} ${year}`;
                                    }
                                    return label;
                                }
                                
                                // Handle month format 
                                if (label && label.includes(' ') && !label.includes('-')) {
                                    const parts = label.split(' ');
                                    if (parts.length === 2) {
                                        const monthName = parts[0];
                                        const year = parts[1];
                                        const monthIndex = ['January', 'February', 'March', 'April', 'May', 'June', 
                                                            'July', 'August', 'September', 'October', 'November', 'December']
                                                            .indexOf(monthName);
                                        if (monthIndex !== -1) {
                                            const firstDay = new Date(year, monthIndex, 1);
                                            const lastDay = new Date(year, monthIndex + 1, 0);
                                            const options = { day: '2-digit', month: 'short' };
                                            return `${firstDay.toLocaleDateString('en-GB', options)} - ${lastDay.toLocaleDateString('en-GB', options)} ${year}`;
                                        }
                                    }
                                    return label;
                                }
                                
                                // Handle year format
                                if (label && !isNaN(label) && label.length === 4) {
                                    return `Full Year ${label}`;
                                }
                                
                                return label;
                            },
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.parsed.y !== undefined) {
                                    label += context.parsed.y;
                                } else {
                                    label += context.parsed;
                                }
                                return label;
                            }
                        },
                        backgroundColor: '#fff',
                        titleColor: '#2c3e50',
                        bodyColor: '#34495e',
                        borderColor: '#bdc3c7',
                        borderWidth: 1
                    }
                }
            }
        });
    }
}