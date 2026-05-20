from odoo import http
from odoo.http import request
from werkzeug.utils import redirect


class LowStockReportController(http.Controller):

    @http.route('/low-stock-report', type='http', auth='user', website=False)
    def low_stock_report(self, company_id=None, **kwargs):
        company_id = int(company_id) if company_id else request.env.company.id
        request.env['product.product'].sudo().get_low_stock_product_ids(company_id)
        return redirect(f"/odoo/action-stock.stock_product_normal_action?cids={company_id}&search_default_below_stock_product=true")