# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Locker status color configuration fields
    available_locker_color = fields.Char(string="Available Locker Color", default="#28A745", help="Color for available lockers (Body Color)")
    allocated_locker_color = fields.Char(string="Allocated Locker Color", default="#DC3545", help="Color for allocated lockers (Body Color)")

    # Automatically create company-specific sequences for lockers and allocations
    @api.model_create_multi
    def create(self, vals_list):
        companies = super().create(vals_list)
        sequence_obj = self.env["ir.sequence"]
        for company in companies:
            sequence_obj.create({"name": f"{company.name} Locker", "code": "locker.locker", "prefix": "LK/%(year)s/", "padding": 5, "number_increment": 1, "company_id": company.id})
            sequence_obj.create({"name": f"{company.name} Locker Allocation", "code": "locker.allocation", "prefix": "LA/%(year)s/", "padding": 5, "number_increment": 1, "company_id": company.id})
        return companies