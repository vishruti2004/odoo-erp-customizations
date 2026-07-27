from odoo import fields, models

class GymExercise(models.Model):
    _name = "gym.exercise"
    _description = "Exercise Master"
    _order = "name"

    name = fields.Char(string="Exercise Name", required=True)
    description = fields.Text(string="Description")
    muscle_group = fields.Selection([
        ("chest", "Chest"),
        ("back", "Back"),
        ("shoulders", "Shoulders"),
        ("biceps", "Biceps"),
        ("triceps", "Triceps"),
        ("legs", "Legs"),
        ("core", "Core"),
        ("cardio", "Cardio"),
        ("full_body", "Full Body"),
    ], string="Muscle Group")
    equipment = fields.Char(string="Equipment")
    active = fields.Boolean(string="Active", default=True)
