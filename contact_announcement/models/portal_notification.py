from odoo import models, fields


class PortalNotification(models.Model):
    _name = "portal.notification"
    _description = "Portal Notification"
    _order = "create_date desc"

    partner_id = fields.Many2one(
        "res.partner",
        required=True
    )

    title = fields.Char(
        required=True
    )

    message = fields.Text()

    is_read = fields.Boolean(
        default=False
    )

    announcement_id = fields.Many2one(
        "contact.announcement",
         ondelete="cascade"
    )