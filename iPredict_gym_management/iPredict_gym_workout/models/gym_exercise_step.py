from odoo import fields, models


class GymExerciseStep(models.Model):
    _name = "gym.exercise.step"
    _description = "Exercise Step"
    _order = "sequence, id"

    exercise_id = fields.Many2one("gym.exercise", string="Exercise", required=True, ondelete="cascade")
    sequence = fields.Integer(string="Step Sequence", default=1, help="Order of the step in the exercise")
    name = fields.Char(string="Step Name", required=True, help="Instructional step for the exercise (e.g., 'Stand with feet shoulder-width apart')")
    image = fields.Image(string="Step Image")
    description = fields.Text(string="Description", help="Detailed description or tips for this step (optional)")