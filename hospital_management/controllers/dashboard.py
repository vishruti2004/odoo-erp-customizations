# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date
from dateutil.relativedelta import relativedelta

class HospitalDashboard(http.Controller):
    @http.route('/hospital/dashboard_data', type='jsonrpc', auth='user')
    def get_data(self):
        today = date.today()
        appt_obj = request.env['hospital.appointment']
        
        start_m = today.replace(day=1)
        next_m = start_m + relativedelta(months=1)
        
        trend_raw = appt_obj._read_group(
            domain=[('start_datetime', '>=', start_m), ('start_datetime', '<', next_m)],
            groupby=['start_datetime:week', 'state'],
            aggregates=['__count']
        )
        
   
        trend_stats = [{'start_datetime:week': w, 'state': s, '__count': c} for w, s, c in trend_raw]

        # 2. Line Chart
        invoices = request.env['account.move'].search([('state', '=', 'posted'), ('move_type', '=', 'out_invoice')])
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        payment_stats = []
        
        for i, m in enumerate(months):
            m_inv = invoices.filtered(lambda x: x.invoice_origin and appt_obj.search([('name', '=', x.invoice_origin)], limit=1).start_datetime.month == (i + 1))
            total_paid = sum(m_inv.mapped(lambda x: x.amount_total - x.amount_residual))
            payment_stats.append({'start_datetime:month': m, '__count': total_paid})

        return {
            "patients": appt_obj.env['hospital.patient'].search_count([]),
            "doctors": appt_obj.env['hospital.doctor'].search_count([]),
            "appointments": appt_obj.search_count([]),
            "state_json": [{'state': s, '__count': c} for s, c in appt_obj._read_group([], groupby=['state'], aggregates=['__count'])],
            "trend_json": trend_stats,
            "payment_json": payment_stats 
        }