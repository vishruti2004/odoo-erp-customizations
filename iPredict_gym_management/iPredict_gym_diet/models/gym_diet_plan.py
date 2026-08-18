# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymDietPlan(models.Model):
    _name = "gym.diet.plan"
    _description = "Diet Plan"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Plan Name", required=True, tracking=True)
    code = fields.Char(string="Plan Code", readonly=True, copy=False, default="New", tracking=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, index=True, tracking=True)
    goal = fields.Selection([("weight_loss", "Weight Loss"), ("weight_gain", "Weight Gain"), ("muscle_gain", "Muscle Gain"), ("fat_loss", "Fat Loss"), ("maintenance", "Maintenance")], string="Goal", required=True, tracking=True)
    days = fields.Integer(string="Diet Days", default=7, tracking=True)
    total_calories = fields.Float(string="Total Calories", compute="_compute_totals", store=True)
    total_protein = fields.Float(string="Total Protein (g)", compute="_compute_totals", store=True)
    total_carbs = fields.Float(string="Total Carbs (g)", compute="_compute_totals", store=True)
    total_fat = fields.Float(string="Total Fat (g)", compute="_compute_totals", store=True)
    meal_line_ids = fields.One2many("gym.diet.meal.line", "diet_id", string="Meals")
    notes = fields.Text(string="Notes", tracking=True)
    assignment_count = fields.Integer(string="Assignments", compute="_compute_assignment_count")

    @api.constrains("company_id")
    def _check_company(self):
        for record in self:
            if not record.company_id:
                raise ValidationError(_("Diet Plan must have a company."))

    def get_end_date(self, start_date):
        self.ensure_one()
        return start_date + timedelta(days=self.days - 1)

    def _compute_assignment_count(self):
        assignment_obj = self.env["gym.diet.assignment"]
        for rec in self:
            member_ids = assignment_obj.search([("plan_id", "=", rec.id), ("company_id", "=", rec.company_id.id)]).mapped("member_id").ids
            rec.assignment_count = len(set(member_ids))

    def action_view_assigned_members(self):
        self.ensure_one()
        assignments = self.env["gym.diet.assignment"].search([("plan_id", "=", self.id), ("company_id", "=", self.company_id.id)])
        member_ids = assignments.mapped("member_id").ids
        expired_member_ids = assignments.filtered(lambda a: a.state == "expired" and not a.is_renewed).mapped("member_id").ids

        return {
            "type": "ir.actions.act_window",
            "name": _("Assigned Members"),
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("id", "in", member_ids), ("company_id", "=", self.company_id.id)],
            "context": {
                "search_default_expired_diet": 1,
                "expired_member_ids": expired_member_ids,
            },
        }

    @api.depends("meal_line_ids.calories", "meal_line_ids.protein", "meal_line_ids.carbs", "meal_line_ids.fat")
    def _compute_totals(self):
        for plan in self:
            plan.total_calories = sum(plan.meal_line_ids.mapped("calories"))
            plan.total_protein = sum(plan.meal_line_ids.mapped("protein"))
            plan.total_carbs = sum(plan.meal_line_ids.mapped("carbs"))
            plan.total_fat = sum(plan.meal_line_ids.mapped("fat"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("company_id"):
                vals["company_id"] = self.env.company.id

            if not vals.get("code") or vals["code"] == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("gym.diet.plan") or "DP0001"

        plans = super().create(vals_list)

        for plan in plans:
            plan.message_post(
                subject=_("Diet Plan Created"),
                body=_("Plan: %s\nCompany: %s\nCreated By: %s") % (
                    plan.name,
                    plan.company_id.name,
                    self.env.user.name,
                ),
            )

        return plans

    def action_open_assign_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Assign Diet Plan"),
            "res_model": "gym.diet.plan.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_plan_id": self.id,
                "default_company_id": self.company_id.id,
            },
        }


class GymDietMealLine(models.Model):
    _name = "gym.diet.meal.line"
    _description = "Diet Meal Line"
    _order = "meal_time, sequence"

    diet_id = fields.Many2one("gym.diet.plan", string="Diet Plan", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", string="Company", related="diet_id.company_id", store=True, readonly=True, index=True)
    sequence = fields.Integer(string="Sequence", default=10)
    start_time = fields.Float(string="Start Time")
    end_time = fields.Float(string="End Time")
    meal_time = fields.Selection([("breakfast", "Breakfast"), ("mid_morning", "Mid-Morning"), ("lunch", "Lunch"), ("evening", "Evening"), ("dinner", "Dinner")], string="Meal", required=True)
    food_id = fields.Many2one("product.template", string="Food Item", required=True, domain="[('is_gym_food', '=', True), '|', ('company_id', '=', False), ('company_id', '=', company_id)]")
    quantity = fields.Float(string="Quantity", default=1, required=True)
    uom_id = fields.Many2one("uom.uom", string="UoM")
    note = fields.Char(string="Instructions")
    calories = fields.Float(related="food_id.calories", string="Calories", store=True, readonly=True)
    protein = fields.Float(related="food_id.protein", string="Protein (g)", store=True, readonly=True)
    carbs = fields.Float(related="food_id.carbs", string="Carbs (g)", store=True, readonly=True)
    fat = fields.Float(related="food_id.fat", string="Fat (g)", store=True, readonly=True)
    meal_category_id = fields.Many2one("product.category", compute="_compute_meal_category", store=False)

    @api.depends("meal_time")
    def _compute_meal_category(self):
        for rec in self:
            rec.meal_category_id = self.env["product.category"].search([("name", "=", rec.meal_time)], limit=1)

    @api.onchange("food_id")
    def _onchange_food_id(self):
        if self.food_id:
            self.uom_id = self.food_id.uom_id

    @api.constrains("start_time", "end_time", "diet_id")
    def _check_overlap(self):
        for rec in self:
            if rec.start_time and rec.end_time:
                if rec.start_time >= rec.end_time:
                    raise ValidationError(_("Start time must be before end time."))

                overlapping = self.search([
                    ("diet_id", "=", rec.diet_id.id),
                    ("id", "!=", rec.id),
                    ("start_time", "<", rec.end_time),
                    ("end_time", ">", rec.start_time),
                ])

                if overlapping:
                    raise ValidationError(_("Time overlaps with another meal."))