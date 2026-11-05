# -*- coding: utf-8 -*-
from odoo import api, models


class O2MCopyPaste(models.AbstractModel):
    _name = "o2m.copy.paste"
    _description = "O2M Copy Paste"

    @api.model
    def get_copy_fields(self, model_name):
        model = self.env[model_name]

        result = {
            name: {
                "copy": field.copy,
                "compute": bool(field.compute),
                "depends": list({
                    dependency.split(".", 1)[0]
                    for dependency in self.pool.field_depends[field]
                }),
            }
            for name, field in model._fields.items()
        }

        return result

    @api.model
    def get_copy_false_setting(self):
        return self.env.company.o2m_copy_false_fields

    @api.model
    def get_copy_paste_enabled(self):
        return self.env.company.o2m_copy_paste_enabled