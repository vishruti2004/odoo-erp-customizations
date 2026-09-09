# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request


class Stock3DController(http.Controller):

    @http.route('/stock_3d/get_data', type='jsonrpc', auth='user')
    def get_3d_data(self):
        """Return 3D warehouse data (locations + stock) as JSON."""
        Location = request.env['stock.location']
        data = Location.get_3d_data()
        return {
            'success': True,
            'data': data
        }