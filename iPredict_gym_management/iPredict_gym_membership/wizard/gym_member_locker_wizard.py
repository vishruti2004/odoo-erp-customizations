# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class GymMemberLockerWizard(models.TransientModel):
    _name = "gym.member.locker.wizard"
    _description = "Assign Locker to Gym Member"

    member_id = fields.Many2one("res.partner", string="Member", required=True, readonly=True)
    locker_id = fields.Many2one("locker.locker", string="Locker", required=True, domain="[('status', '=', 'available')]")
    start_date = fields.Date(string="Start Date", required=True, default=fields.Date.today)
    end_date = fields.Date(string="End Date", required=True)

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for wizard in self:
            if wizard.start_date and wizard.end_date and wizard.end_date < wizard.start_date:
                raise ValidationError(_("End Date must be greater than or equal to Start Date."))

    def action_assign_locker(self):
        self.ensure_one()

        # Check if the locker is already allocated
        existing_allocation = self.env["locker.allocation"].search(
            [
                ("locker_id", "=", self.locker_id.id),
                ("state", "=", "allocated"),
            ],
            limit=1,
        )
        if existing_allocation:
            raise ValidationError(_("This locker is already allocated."))

        # Create Locker Allocation
        allocation = self.env["locker.allocation"].create(
            {
                "locker_id": self.locker_id.id,
                "partner_id": self.member_id.id,
                "start_date": self.start_date,
                "end_date": self.end_date,
            }
        )

        # Allocate the locker
        allocation.action_allocate()

        # Create Gym Member Locker relation
        self.env["gym.member.locker"].create(
            {
                "member_id": self.member_id.id,
                "allocation_id": allocation.id,
            }
        )

        return {"type": "ir.actions.act_window_close"}