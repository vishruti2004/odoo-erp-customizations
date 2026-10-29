# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.fields import Domain


class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    cheapest_exclude_product_ids = fields.Many2many(
        'product.product',
        relation='loyalty_reward_exclude_product_rel',
        string="Exclude Products",
        help="Products ignored when finding the cheapest product.",   
    )
    cheapest_exclude_categ_ids = fields.Many2many(
        'product.category',
        relation='loyalty_reward_exclude_categ_rel',
        string="Exclude Categories",
        help="Categories whose products are ignored when finding the cheapest product.",
    )
    is_exclude_child_categ = fields.Boolean(
        string="Is Exclude Child Categories",
        help="Also ignore products of the subcategories.",
    )

    def _get_discount_product_domain(self):
        domain = super()._get_discount_product_domain()
        if self.discount_applicability != 'cheapest':
            return domain
        categories = self.cheapest_exclude_categ_ids
        if categories and self.is_exclude_child_categ:
            categories = self.env['product.category'].search([('id', 'child_of', categories.ids)])
        if self.cheapest_exclude_product_ids:
            domain &= Domain('id', 'not in', self.cheapest_exclude_product_ids.ids)
        if categories:
            domain &= Domain('categ_id', 'not in', categories.ids)
        return domain
