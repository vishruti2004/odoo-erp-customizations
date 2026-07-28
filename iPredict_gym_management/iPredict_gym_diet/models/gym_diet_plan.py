from odoo import fields, models, api


class GymDietPlan(models.Model):
    _name = "gym.diet.plan"
    _description = "Diet Plan"
    _order = "id desc"

    name = fields.Char(string="Plan Name", required=True)
    code = fields.Char(string="Plan Code", readonly=True, copy=False, default="New")

    goal = fields.Selection([("weight_loss", "Weight Loss"), ("weight_gain", "Weight Gain"), ("muscle_gain", "Muscle Gain"), ("fat_loss", "Fat Loss"), ("maintenance", "Maintenance")], string="Goal", required=True)

    days = fields.Integer(string="Workout Days", default=0)

    total_calories = fields.Float(string="Total Calories", compute="_compute_totals", store=True)
    total_protein = fields.Float(string="Total Protein (g)", compute="_compute_totals", store=True)
    total_carbs = fields.Float(string="Total Carbs (g)", compute="_compute_totals", store=True)
    total_fat = fields.Float(string="Total Fat (g)", compute="_compute_totals", store=True)

    meal_line_ids = fields.One2many("gym.diet.meal.line", "diet_id", string="Meals")

    notes = fields.Text(string="Notes")

    @api.depends(
        "meal_line_ids.calories",
        "meal_line_ids.protein",
        "meal_line_ids.carbs",
        "meal_line_ids.fat",
    )
    def _compute_totals(self):
        for plan in self:
            plan.total_calories = sum(plan.meal_line_ids.mapped("calories"))
            plan.total_protein = sum(plan.meal_line_ids.mapped("protein"))
            plan.total_carbs = sum(plan.meal_line_ids.mapped("carbs"))
            plan.total_fat = sum(plan.meal_line_ids.mapped("fat"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") or vals["code"] == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("gym.diet.plan") or "DP0001"
        return super().create(vals_list)

    def action_open_assign_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Assign Diet Plan",
            "res_model": "gym.diet.plan.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_plan_id": self.id,
            },
        }


class GymDietMealLine(models.Model):
    _name = "gym.diet.meal.line"
    _description = "Diet Meal Line"
    _order = "meal_time, sequence"

    diet_id = fields.Many2one("gym.diet.plan", string="Diet Plan", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Sequence", default=10)

    meal_time = fields.Selection([("breakfast", "Breakfast"), ("mid_morning", "Mid-Morning"), ("lunch", "Lunch"), ("evening", "Evening"), ("dinner", "Dinner")], string="Meal Time", required=True)

    food_id = fields.Many2one("gym.food", string="Food Item", required=True, help="Dropdown auto-filters based on the selected Meal Time.")
    quantity = fields.Char(string="Quantity", required=True, help="e.g. 100g, 1 bowl, 2 pieces")
    note = fields.Char(string="Instructions", help="e.g. 'Without Sugar', 'Less Oil'")

    calories = fields.Float(related="food_id.calories", string="Calories", store=True, readonly=True)
    protein = fields.Float(related="food_id.protein", string="Protein (g)", store=True, readonly=True)
    carbs = fields.Float(related="food_id.carbs", string="Carbs (g)", store=True, readonly=True)
    fat = fields.Float(related="food_id.fat", string="Fat (g)", store=True, readonly=True)