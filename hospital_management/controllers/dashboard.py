from odoo import http, fields
from odoo.http import request
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import calendar

class HospitalDashboard(http.Controller):
    @http.route('/hospital/dashboard_data', type='jsonrpc', auth='user')
    def get_data(self, period='month', trend_period='all', year=None, **kw):
        today = date.today()
        appt_obj = request.env['hospital.appointment']
        
        state_selection = dict(appt_obj.fields_get(['state'])['state']['selection'])

        trend_domain = []
        
        if trend_period == 'all':
            group_by_field = 'start_datetime:year'
            trend_domain = []
            
        elif trend_period == 'this_year':
            group_by_field = 'start_datetime:month'
            start_date = today.replace(month=1, day=1)
            trend_domain = [('start_datetime', '>=', start_date),
                            ('start_datetime', '<', start_date + relativedelta(years=1))]
                            
        elif trend_period == 'previous_year':
            group_by_field = 'start_datetime:month'
            start_date = (today - relativedelta(years=1)).replace(month=1, day=1)
            trend_domain = [('start_datetime', '>=', start_date),
                            ('start_datetime', '<', start_date + relativedelta(years=1))]
                            
        elif trend_period == 'selected_year':
            group_by_field = 'start_datetime:month'
            if year:
                start_date = date(int(year), 1, 1)
                end_date = date(int(year), 12, 31)
                trend_domain = [('start_datetime', '>=', start_date),
                                ('start_datetime', '<=', end_date)]
        else:
            group_by_field = 'start_datetime:week'
            if trend_period == 'this_month':
                start_date = today.replace(day=1)
                trend_domain = [('start_datetime', '>=', start_date),
                                ('start_datetime', '<', start_date + relativedelta(months=1))]
            elif trend_period == 'previous_month':
                start_date = (today - relativedelta(months=1)).replace(day=1)
                trend_domain = [('start_datetime', '>=', start_date),
                                ('start_datetime', '<', start_date + relativedelta(months=1))]
            elif trend_period == 'next_month':
                start_date = (today + relativedelta(months=1)).replace(day=1)
                trend_domain = [('start_datetime', '>=', start_date),
                                ('start_datetime', '<', start_date + relativedelta(months=1))]

        trend_raw = appt_obj._read_group(
            domain=trend_domain,
            groupby=[group_by_field, 'state'],
            aggregates=['__count']
        )
        
        trend_stats = []
        for val, state, count in trend_raw:
            formatted_label = self._format_label(val, group_by_field)
            trend_stats.append({
                'label': formatted_label if val else "Unknown",
                'state': state_selection.get(state, state),
                '__count': count,
                'raw_date': val
            })

        available_years = []
        all_years_raw = appt_obj._read_group(
            domain=[],
            groupby=['start_datetime:year'],
            aggregates=['__count']
        )
        
        for val, count in all_years_raw:
            if val:
                if isinstance(val, (datetime, date)):
                    available_years.append(val.year)
                elif isinstance(val, (int, float)):
                    available_years.append(int(val))
                elif isinstance(val, str):
                    try:
                        available_years.append(int(val))
                    except:
                        pass
                else:
                    try:
                        if hasattr(val, 'year'):
                            available_years.append(val.year)
                    except:
                        pass
        
        available_years = sorted(list(set(available_years)))

        # TOP DOCTORS LOGIC ---
        if period == 'month':
            doc_start = today.replace(day=1)
            doc_end = doc_start + relativedelta(months=1)
        else:
            doc_start = today.replace(month=1, day=1)
            doc_end = doc_start + relativedelta(years=1)

        top_doctors_raw = appt_obj._read_group(
            domain=[('start_datetime', '>=', doc_start), ('start_datetime', '<', doc_end),
                    ('doctor_id', '!=', False), ('state', 'in', ['confirm', 'consult', 'done'])],
            groupby=['doctor_id'], aggregates=['__count'], limit=5, order='__count desc'
        )
        top_doctors = [{'name': doctor.display_name, 'count': count} for doctor, count in top_doctors_raw if doctor]

        # --- 5. PAYMENT LINE CHART (By Month) ---
        invoices = request.env['account.move'].search([('state', '=', 'posted'), ('move_type', '=', 'out_invoice')])
        months_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        payment_stats = []
        for i, m in enumerate(months_list):
            m_inv = invoices.filtered(lambda x: x.invoice_date and x.invoice_date.month == (i + 1) and x.invoice_date.year == today.year)
            total_paid = sum(m_inv.mapped(lambda x: x.amount_total - x.amount_residual))
            payment_stats.append({'label': m, '__count': total_paid})

        return {
            "top_doctors": top_doctors,
            "patients": appt_obj.env['hospital.patient'].search_count([]),
            "doctors": appt_obj.env['hospital.doctor'].search_count([]),
            "today_appointments": appt_obj.search_count([('start_datetime', '>=', f"{today} 00:00:00"),
                                                        ('start_datetime', '<=', f"{today} 23:59:59")]),
            "currency_symbol": request.env.company.currency_id.symbol,
            "state_json": [{'state': state_selection.get(s, s), '__count': c}
                          for s, c in appt_obj._read_group([], groupby=['state'], aggregates=['__count'])],
            "trend_json": trend_stats,
            "payment_json": payment_stats,
            "available_years": available_years
        }
    
    def _format_label(self, val, group_by_field):
        """Format label based on grouping type"""
        if not val:
            return "Unknown"
        
        if 'year' in group_by_field:
            # Just return the year
            if isinstance(val, (datetime, date)):
                return str(val.year)
            return str(val)
        elif 'month' in group_by_field:
            # Format as month name and year
            if isinstance(val, (datetime, date)):
                return val.strftime('%B %Y')
            return str(val)
        elif 'week' in group_by_field:
            # Format as week number and year
            if isinstance(val, (datetime, date)):
                week_num = val.isocalendar()[1]
                return f"W{week_num} {val.year}"
            return str(val)
        return str(val)