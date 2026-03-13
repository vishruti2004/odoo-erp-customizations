from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

class HospitalLogin(Home):

    def _is_patient_user(self, uid):
        """User Patient che ke nahi e check karva mate sudo logic"""
        if not uid:
            return False
        
        # Admin redirect on backend 
        user = request.env['res.users'].sudo().browse(uid)
        if user._is_system():
            return False

        # Company check 

        company = request.env['res.company'].sudo().search([], limit=1)
        if not company.patient_portal_access_only:
            return False

        # Hospital patient record check
        patient = request.env['hospital.patient'].sudo().search([
            ('user_id', '=', uid)
        ], limit=1)
        return bool(patient)

    @http.route(['/web', '/odoo', '/odoo/<path:subpath>'], type='http', auth="none")
    def web_client(self, s_action=None, **kw):
        """Backend rasta bandh karva mate"""
        # Session check kare 
        if request.session.uid and self._is_patient_user(request.session.uid):
            return request.redirect('/my', 303)
        
        # Jo patient nathi, to original backend 
        return super().web_client(s_action=s_action, **kw)

    @http.route('/web/login', type='http', auth="public", website=True)
    def web_login(self, redirect=None, **kw):
        response = super().web_login(redirect=redirect, **kw)

        # Jo login successful thayu hoy
        if request.session.uid and self._is_patient_user(request.session.uid):
            return request.redirect('/my', 303)

        return response