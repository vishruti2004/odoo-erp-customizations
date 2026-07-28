from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class GymWorkoutPlan(models.Model):
    _name = "gym.workout.plan"
    _description = "Workout Plan"
    _order = "id desc"

    name = fields.Char(string="Plan Name", required=True)
    code = fields.Char(string="Plan Code", readonly=True, copy=False, default="New")
    days = fields.Integer(string="Workout Days", default=0)

    exercise_line_ids = fields.One2many("gym.workout.plan.exercise.line", "plan_id", string="Exercise List")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("code") or vals["code"] == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("gym.workout.plan") or "WP0001"
        return super().create(vals_list)

    def action_open_assign_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Assign Workout Plan",
            "res_model": "gym.workout.plan.assign.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_plan_id": self.id,
            },
        }


class GymWorkoutPlanExerciseLine(models.Model):
    _name = "gym.workout.plan.exercise.line"
    _description = "Workout Plan Exercise Line"
    _order = "day, sequence"

    plan_id = fields.Many2one("gym.workout.plan", string="Workout Plan", required=True, ondelete="cascade")
    day = fields.Selection([("monday", "Monday"), ("tuesday", "Tuesday"), ("wednesday", "Wednesday"), ("thursday", "Thursday"), ("friday", "Friday"), ("saturday", "Saturday"), ("sunday", "Sunday")], string="Day", required=True, default="monday")
    exercise_id = fields.Many2one("gym.exercise", string="Exercise", required=True)
    sets = fields.Integer(string="Sets")
    reps = fields.Char(string="Reps")
    rest = fields.Char(string="Rest Time")
    sequence = fields.Integer(string="Sequence", default=10)
    exercise_step_ids = fields.Many2many("gym.exercise.step", compute="_compute_exercise_steps", string="Exercise Steps")
    exercise_image = fields.Image(related="exercise_id.image", string="Exercise Image", readonly=True)
    exercise_video_url = fields.Char(related="exercise_id.video_url", string="Video URL", readonly=True)

    @api.depends("exercise_id")
    def _compute_exercise_steps(self):
        for rec in self:
            rec.exercise_step_ids = rec.exercise_id.step_ids