# -*- coding: utf-8 -*-

from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        sequence_obj = self.env["ir.sequence"]

        for company in companies:
            # Locker Sequence
            sequence_obj.create({"name": f"{company.name} Locker", "code": "locker.locker", "prefix": "LK/%(year)s/", "padding": 5, "number_increment": 1, "company_id": company.id})

            # Locker Allocation Sequence
            sequence_obj.create({"name": f"{company.name} Locker Allocation", "code": "locker.allocation", "prefix": "LA/%(year)s/", "padding": 5, "number_increment": 1, "company_id": company.id})

        return companies