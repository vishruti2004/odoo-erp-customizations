from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home

class AttendanceHome(Home):

    @http.route('/web/session/logout', type='http', auth='none')
    def logout(self, redirect='/odoo/discuss', **kw):
        request.session.logout(keep_db=True)
        return request.redirect('/odoo/discuss')