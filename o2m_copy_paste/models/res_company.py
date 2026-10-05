from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    o2m_copy_false_fields = fields.Boolean(
        string="Copy fields with copy=False",
        default=False,
        help="If enabled, fields with copy=False will also be copied "
             "when using O2M Copy/Paste.",
    )