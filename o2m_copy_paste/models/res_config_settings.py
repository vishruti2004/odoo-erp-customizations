from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    o2m_copy_false_fields = fields.Boolean(
        related="company_id.o2m_copy_false_fields",
        readonly=False,
        string="Copy fields with copy=False",
    )