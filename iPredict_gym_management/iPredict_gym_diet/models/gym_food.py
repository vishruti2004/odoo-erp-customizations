from odoo import fields, models


class GymFood(models.Model):
    _name = "gym.food"
    _description = "Food Master"
    _order = "name"

    name = fields.Char(string="Food Name", required=True)
    active = fields.Boolean(string="Active", default=True)

    meal_category = fields.Selection([("breakfast", "Breakfast"), ("mid_morning", "Mid-Morning"), ("lunch", "Lunch"), ("evening", "Evening"), ("dinner", "Dinner")], string="Meal Category", required=True, help="Which meal time this food is suited for — used to filter the Food dropdown in the Diet Plan's Meal Lines.")

    calories = fields.Float(string="Calories", required=True, help="Calories per serving")
    protein = fields.Float(string="Protein (g)")
    carbs = fields.Float(string="Carbs (g)")
    fat = fields.Float(string="Fat (g)")
