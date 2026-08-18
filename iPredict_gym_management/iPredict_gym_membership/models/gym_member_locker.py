# -*- coding: utf-8 -*-

from odoo import fields, models


class GymMemberLocker(models.Model):
    _name = "gym.member.locker"
    _description = "Gym Member Locker"

    member_id = fields.Many2one(
        "res.partner",
        string="Member",
        required=True,
    )

    allocation_id = fields.Many2one(
        "locker.allocation",
        string="Locker Allocation",
        required=True,
    )