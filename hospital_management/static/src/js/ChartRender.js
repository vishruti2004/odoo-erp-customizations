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
        
        //   JSON.stringify - update properly
        useEffect(() => { 
            this.renderChart(); 
        }, () => [JSON.stringify(this.props.data)]);
        
        onWillUnmount(() => { if (this.chart) this.chart.destroy(); });
    }

    getWeekNumber(d) {
        d = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
        d.setUTCDate(d.getUTCDate() + 4 - (d.getUTCDay() || 7));
        var yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
        var weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
        return weekNo;
    }

    renderChart() {
        if (!this.props.data || !this.chartRef.el) return;
        if (this.chart) this.chart.destroy();

        const self = this;
        const type = this.props.type ? this.props.type.toLowerCase() : 'bar';
        const isCircular = (type === 'pie' || type === 'doughnut');
        let datasets = [];

        if (type === 'bar') {
            datasets = (this.props.data.datasets || []).map(ds => ({
                ...ds,
                backgroundColor: this.stateColors[ds.label] || '#cccccc',
                borderWidth: 1
            }));
        }
        else if (type === 'line') {
            datasets = [{
                label: 'Total Amount',
                data: this.props.data.counts || [],
                borderColor: '#219d9b',
                backgroundColor: 'rgba(33, 157, 155, 0.1)',
                fill: true, tension: 0.4, borderWidth: 3
            }];
        }
        else {
            const bgColors = (this.props.data.labels || []).map(l => this.stateColors[l] || '#cccccc');
            datasets = [{
                data: this.props.data.counts || [],
                backgroundColor: bgColors,
                hoverOffset: 15
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
                            callback: function(val, index) {
                                const label = this.getLabelForValue(val);
                                const dateRangeMatch = label.match(/(\d+)-(\d+)\s(\w+)/);
                                if (dateRangeMatch) {
                                    const month = dateRangeMatch[3];
                                    const monthNames = {'Jan':'01','Feb':'02','Mar':'03','Apr':'04','May':'05','Jun':'06',
                                                      'Jul':'07','Aug':'08','Sep':'09','Oct':'10','Nov':'11','Dec':'12'};
                                    const monthNum = monthNames[month];
                                    const year = new Date().getFullYear();
                                    const startDate = new Date(year, parseInt(monthNum)-1, parseInt(dateRangeMatch[1]));
                                    const weekNum = self.getWeekNumber(startDate);
                                    return `W${weekNum}`;
                                }
                                return label;
                            }
                        }
                    },
                    y: { 
                        display: !isCircular, 
                        stacked: type === 'bar', 
                        beginAtZero: true,
                        ticks: {
                            callback: function(val) {
                                if (self.props.currency) {
                                    return self.props.currency + ' ' + val;
                                }
                                return val;
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: type !== 'line',
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 20 }
                    },
                    tooltip: {
                        callbacks: {
                            title: function(context) {
                                const label = context[0].label;
                                const weekMatch = label.match(/(\d+)-(\d+)\s(\w+)/);
                                if (weekMatch) {
                                    const startDay = weekMatch[1];
                                    const endDay = weekMatch[2];
                                    const month = weekMatch[3];
                                    const currentYear = new Date().getFullYear();
                                    return `${startDay} ${month} ${currentYear} - ${endDay} ${month} ${currentYear}`;
                                }
                                const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 
                                                   'July', 'August', 'September', 'October', 'November', 'December'];
                                if (monthNames.includes(label)) {
                                    const monthIndex = monthNames.indexOf(label);
                                    const currentYear = new Date().getFullYear();
                                    const lastDay = new Date(currentYear, monthIndex + 1, 0).getDate();
                                    return `1 ${label.substring(0,3)} ${currentYear} - ${lastDay} ${label.substring(0,3)} ${currentYear}`;
                                }
                                if (label && !isNaN(label) && label.length === 4) {
                                    return ` Year ${label}`;
                                }
                                return label;
                            },
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) { label += ': '; }
                                if (context.parsed.y !== undefined) {
                                    if (self.props.currency) {
                                        label += self.props.currency + ' ' + context.parsed.y;
                                    } else {
                                        label += context.parsed.y;
                                    }
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