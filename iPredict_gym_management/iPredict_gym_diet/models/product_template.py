# -*- coding: utf-8 -*-

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_gym_food = fields.Boolean(string="Gym Food")
    calories = fields.Float(string="Calories", help="Calories per serving")
    protein = fields.Float(string="Protein (g)")
    carbs = fields.Float(string="Carbs (g)")
    fat = fields.Float(string="Fat (g)")