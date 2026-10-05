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
                "type": field.type,
                "compute": bool(field.compute),
            }
            for name, field in model._fields.items()
        }

        print(
            "O2M COPY FIELD CHECK:",
            model_name,
            result.get("qty_received_manual"),
        )

        return result

    @api.model
    def get_copy_false_setting(self):
        value = self.env.company.o2m_copy_false_fields

        print(
            "O2M COPY FALSE SETTING:",
            {
                "company_id": self.env.company.id,
                "company": self.env.company.name,
                "value": value,
            },
        )

        return value