from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

class LockerReturnWizard(models.TransientModel):
    _name = "locker.return.wizard"
    _description = "Locker Return Wizard"

    allocation_id = fields.Many2one("locker.allocation", string="Locker Allocation", required=True, readonly=True)
    locker_id = fields.Many2one("locker.locker", string="Locker", compute="_compute_locker_id", store=True, readonly=True)
    return_date = fields.Date(string="Return Date", required=True, default=fields.Date.context_today)
    return_reason_id = fields.Many2one("locker.return.reason", string="Return Reason", required=True, domain="[('active', '=', True)]")

    @api.depends("allocation_id.locker_id")
    def _compute_locker_id(self):
        for wizard in self:
            wizard.locker_id = wizard.allocation_id.locker_id

    def action_confirm_return(self):
        self.ensure_one()
        allocation = self.allocation_id

        if allocation.state not in ("allocated", "renewal_pending", "expired"):
            raise ValidationError(
                _("Locker return is not allowed in the current state.")
            )

        allocation.write({
            "end_date": self.return_date,
            "return_date": self.return_date,
            "return_reason_id": self.return_reason_id.id,
            "renewal_available": False,
            "state": "returned",
        })

        if allocation.locker_id:
            allocation.locker_id.status = "available"

        allocation.message_post(
            body=_("Locker returned on %s. Return Reason: %s") % (
                self.return_date,
                self.return_reason_id.display_name,
            )
        )

        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }