from odoo import models

class MrpBom(models.Model):
    _inherit = "mrp.bom"

    def _get_phase_bom_lines(self, operation):
        """
        Return only those BoM component lines which are mapped
        to the given operation.
        """
        self.ensure_one()
        return self.bom_line_ids.filtered(
            lambda line: line.operation_id == operation
        )