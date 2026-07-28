from odoo import fields, models


class GymExercise(models.Model):
    _name = "gym.exercise"
    _description = "Exercise"
    _order = "name"

    name = fields.Char(string="Exercise Name", required=True)
    active = fields.Boolean(string="Active", default=True)

    muscle_group = fields.Selection([("legs", "Legs"), ("chest", "Chest"), ("back", "Back"), ("shoulders", "Shoulders"), ("biceps", "Biceps"), ("triceps", "Triceps"), ("core", "Core"), ("cardio", "Cardio"), ("full_body", "Full Body")], string="Muscle Group")

    equipment = fields.Char(string="Equipment")
    description = fields.Text(string="Description")

    step_ids = fields.One2many("gym.exercise.step", "exercise_id", string="Steps")
    step_count = fields.Integer(string="Step Count", compute="_compute_step_count")

    image = fields.Image(string="Exercise Image")
    video_url = fields.Char(string="Video URL")

    def _compute_step_count(self):
        for rec in self:
            rec.step_count = len(rec.step_ids)