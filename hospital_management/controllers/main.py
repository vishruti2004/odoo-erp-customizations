from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

class HospitalLogin(Home):

    def _is_restricted_patient(self, uid):
        if not uid:
            return False
        
        user = request.env["res.users"].sudo().browse(uid)
        company = request.env.company

        if not user.partner_id.is_patient:
            return False

        if not company.patient_portal_access_only:
            return False

        allowed_patients = company.portal_patient_ids.ids

        if not allowed_patients:
            return True

        if user.partner_id.id in allowed_patients:
            return True

        return False

    @http.route(["/web", "/odoo", "/odoo/<path:subpath>"], type="http", auth="user")
    def web_client(self, s_action=None, **kw):

        if self._is_restricted_patient(request.session.uid):
            return request.redirect("/my", 303)

        return super().web_client(s_action=s_action, **kw)

    @http.route("/web/login", type="http", auth="public", website=True)
    def web_login(self, redirect=None, **kw):
        response = super().web_login(redirect=redirect, **kw)

        if request.session.uid and self._is_restricted_patient(request.session.uid):
            return request.redirect("/my", 303)

        return response