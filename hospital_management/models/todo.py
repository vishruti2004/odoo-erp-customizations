from odoo import models, fields

class HospitalTodo(models.Model):
    _name = "hospital.todo"
    _description = "Hospital Todo List"

    description = fields.Char(string="Task", required=True)
    
    is_completed = fields.Boolean(string="Completed", default=False)
    
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)