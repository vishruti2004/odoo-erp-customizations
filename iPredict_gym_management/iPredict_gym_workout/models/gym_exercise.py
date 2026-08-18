# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class GymExercise(models.Model):
    _name = "gym.exercise"
    _description = "Exercise"
    _order = "name"

    name = fields.Char(string="Exercise Name", required=True)
    active = fields.Boolean(string="Active", default=True)
    company_id = fields.Many2one("res.company", string="Company", required=True, default=lambda self: self.env.company, index=True)
    muscle_group = fields.Selection([("legs", "Legs"), ("chest", "Chest"), ("back", "Back"), ("shoulders", "Shoulders"), ("biceps", "Biceps"), ("triceps", "Triceps"), ("core", "Core"), ("cardio", "Cardio"), ("full_body", "Full Body")], string="Muscle Group")
    equipment_id = fields.Many2one("maintenance.equipment", string="Equipment", domain="[('company_id', '=', company_id)]", ondelete="restrict")
    description = fields.Text(string="Description")
    step_ids = fields.One2many("gym.exercise.step", "exercise_id", string="Steps")
    step_count = fields.Integer(string="Step Count", compute="_compute_step_count")
    image = fields.Image(string="Exercise Image")
    video_url = fields.Char(string="Video URL")

    @api.depends("step_ids")
    def _compute_step_count(self):
        for rec in self:
            rec.step_count = len(rec.step_ids)