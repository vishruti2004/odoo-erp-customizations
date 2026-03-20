# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import date

class HospitalDashboard(http.Controller):
    @http.route('/hospital/dashboard_data', type='jsonrpc', auth='user')
    def get_data(self):
        today = date.today()
        today_count = request.env['hospital.appointment'].sudo().search_count([
            ('start_datetime', '>=', f"{today} 00:00:00"),
            ('start_datetime', '<=', f"{today} 23:59:59"),
            ('state', 'in', ['confirm', 'consult', 'done']) 
        ])
        appointment_states = request.env['hospital.appointment'].sudo().read_group(
            domain=[],
            fields=['state'],
            groupby=['state']
        )

        return {
            "patients": request.env['hospital.patient'].sudo().search_count([]),
            "doctors": request.env['hospital.doctor'].sudo().search_count([]),
            "appointments": request.env['hospital.appointment'].sudo().search_count([]),
            "today_appointments": today_count,
            "state_json": appointment_states 
        }