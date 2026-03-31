from odoo import http, fields
from odoo.http import request
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import calendar
from collections import defaultdict

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
        else:
            group_by_field = 'start_datetime:day'
            if trend_period == 'this_month':
                start_date = today.replace(day=1)
                end_date = today.replace(day=calendar.monthrange(today.year, today.month)[1])
                trend_domain = [('start_datetime', '>=', start_date),
                                ('start_datetime', '<=', end_date)]
                
            elif trend_period == 'previous_month':
                start_date = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
                end_date = start_date.replace(day=calendar.monthrange(start_date.year, start_date.month)[1])
                trend_domain = [('start_datetime', '>=', start_date),
                                ('start_datetime', '<=', end_date)]
                
            elif trend_period == 'next_month':
                start_date = (today.replace(day=calendar.monthrange(today.year, today.month)[1]) + timedelta(days=1))
                end_date = start_date.replace(day=calendar.monthrange(start_date.year, start_date.month)[1])
                trend_domain = [('start_datetime', '>=', start_date),
                                ('start_datetime', '<=', end_date)]

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
        
        # Group days into weeks for month view
        if trend_period in ['this_month', 'previous_month', 'next_month']:
            week_data = defaultdict(lambda: defaultdict(int))
            month_end = end_date
            
            for item in trend_stats:
                if item['raw_date']:
                    date_obj = item['raw_date']
                    if isinstance(date_obj, datetime):
                        date_obj = date_obj.date()
                    
                    weekday = date_obj.weekday()
                    if weekday == 6:
                        week_start = date_obj
                    else:
                        week_start = date_obj - timedelta(days=weekday + 1)
                    
                    week_end = week_start + timedelta(days=6)
                    if week_end > month_end:
                        week_end = month_end
                    
                    week_label = f"{week_start.day}-{week_end.day} {week_start.strftime('%b')}"
                    week_data[week_label][item['state']] += item['__count']
            
            trend_stats = []
            for week_label, states in week_data.items():
                for state, count in states.items():
                    trend_stats.append({
                        'label': week_label,
                        'state': state,
                        '__count': count
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
        
        available_years = sorted(list(set(available_years)))

        # TOP DOCTORS LOGIC
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

        # TOTAL APPOINTMENTS AND TOTAL DONE
        total_appointments = appt_obj.search_count([])
        total_done_count = appt_obj.search_count([('state', '=', 'done')])

        # PAYMENT CHART - APPOINTMENT WISE
        months_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        payment_stats = []
        total_payment_year = 0
        
        for i, m in enumerate(months_list):
            month_num = i + 1
            if month_num == 12:
                start_date = date(today.year, month_num, 1)
                end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                start_date = date(today.year, month_num, 1)
                end_date = date(today.year, month_num + 1, 1) - timedelta(days=1)
            
            month_appointments = appt_obj.search([
                ('start_datetime', '>=', start_date),
                ('start_datetime', '<=', end_date),
                ('payment_done', '=', True),
                ('state', 'in', ['confirm', 'consult', 'done'])
            ])
            
            total_paid = sum(appt.consultation_fee or 0 for appt in month_appointments)
            payment_stats.append({'label': m, '__count': total_paid})
            total_payment_year += total_paid

        return {
            "top_doctors": top_doctors,
            "patients": appt_obj.env['hospital.patient'].search_count([]),
            "doctors": appt_obj.env['hospital.doctor'].search_count([]),
            "today_appointments": appt_obj.search_count([
                ('start_datetime', '>=', f"{today} 00:00:00"),
                ('start_datetime', '<=', f"{today} 23:59:59"),
                ('state', 'in', ['confirm', 'consult', 'done']) 
            ]),
            "total_appointments": total_appointments,
            "total_done_count": total_done_count,
            "total_payment_year": total_payment_year,
            "currency_symbol": request.env.company.currency_id.symbol,
            "state_json": [{'state': state_selection.get(s, s), '__count': c}
                          for s, c in appt_obj._read_group([], groupby=['state'], aggregates=['__count'])],
            "trend_json": trend_stats,
            "payment_json": payment_stats,
            "available_years": available_years
        }
    
    def _format_label(self, val, group_by_field):
        if not val:
            return "Unknown"
        
        if 'year' in group_by_field:
            if isinstance(val, (datetime, date)):
                return str(val.year)
            return str(val)
        elif 'month' in group_by_field:
            if isinstance(val, (datetime, date)):
                return val.strftime('%B')
            return str(val)
        elif 'day' in group_by_field:
            if isinstance(val, (datetime, date)):
                return str(val.day)
            return str(val)
        return str(val)