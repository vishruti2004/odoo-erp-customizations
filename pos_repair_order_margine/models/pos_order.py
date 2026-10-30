from odoo import _, models

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_repair_full_margin(self):
        lines = self.lines.filtered(lambda line: line._is_full_margin())
        updated = lines._repair_total_cost()
        skipped = len(lines - updated)

        if not lines:
            message = _("No order lines with a 100% margin found.")
        elif skipped:
            message = _("Cost updated on %(updated)s line(s). %(skipped)s skipped: no purchase price found.",
                        updated=len(updated), skipped=skipped)
        else:
            message = _("Cost updated on %(updated)s line(s).", updated=len(updated))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Margin Repair"),
                'message': message,
                'type': 'success' if updated else 'warning',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }
