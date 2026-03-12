from odoo import models, fields


class HospitalSpecialization(models.Model):
    _name = 'hospital.specialization'
    _description = 'Hospital Specialization'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Name", required=True, tracking=True)
    code = fields.Char(string="Code", required=True, tracking=True)
    description = fields.Text(string="Description", tracking=True)
    active = fields.Boolean(default=True, tracking=True)

    # Correct One2many
    doctor_ids = fields.One2many(
        'hospital.doctor',
        'specialization_id',
        string="Doctors"
    )

    doctor_count = fields.Integer(
        string="Doctor Count",
        compute="_compute_doctor_count"
    )

    # Count Doctors
    def _compute_doctor_count(self):
        for record in self:
            record.doctor_count = len(record.doctor_ids)

    # Smart Button Action
    def action_open_doctor(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Doctors',
            'view_mode': 'list,form',
            'res_model': 'hospital.doctor',
            'domain': [('specialization_id', '=', self.id)],
            'context': {
                'default_specialization_id': self.id
            },
        }