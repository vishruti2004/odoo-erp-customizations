# -*- coding: utf-8 -*-
from odoo import models

class WebsiteSnippetFilter(models.Model):
    _inherit = 'website.snippet.filter'

    #1. run _prepare_values methods = get model name and return doctor data in _record -- not call website_sale

    def _prepare_values(self, limit=None, search_domain=None, res_model=None, res_id=None):
        model_name = res_model or self.model_name
        
        if model_name == 'hospital.doctor':
            domain = search_domain or []
            records = self.env[model_name].sudo().search(domain, limit=limit)
            result = []
            for record in records:
                vals = {
                    '_record': record,
                }
                result.append(vals)
            return result
        
        return super()._prepare_values(limit=limit, search_domain=search_domain, res_model=res_model, res_id=res_id)
    
    #2. get data from _prepare_values - filter into dict
    
    def _filter_records_to_values(self, records, **options):
        res_model = options.get('res_model') or self.model_name
        
        if res_model == 'hospital.doctor':
            result = []
            for record in records:
                vals = {
                    '_record': record,
                }
                result.append(vals)
            return result
        
        return super()._filter_records_to_values(records, **options)