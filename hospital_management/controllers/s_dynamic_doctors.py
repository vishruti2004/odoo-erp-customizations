from odoo import models

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    def _prepare_values(self, limit=None, search_domain=None, **kwargs):
        return super()._prepare_values(limit=limit, search_domain=search_domain, **kwargs)

    def _get_filter_records(self, website):
        if self.model_name == 'hospital.doctor':

            print("=-============fetch data==========")
            return self.env['hospital.doctor'].search([], limit=self.limit)
        return super()._get_filter_records(website)