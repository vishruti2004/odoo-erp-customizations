# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    o2m_copy_paste_enabled = fields.Boolean(
        related="company_id.o2m_copy_paste_enabled",
        readonly=False,
        string="Enable O2M Copy/Paste in List View",
    )

    o2m_copy_false_fields = fields.Boolean(
        related="company_id.o2m_copy_false_fields",
        readonly=False,
        string="Copy fields with copy=False",
    )