from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class KitchenRuleError(UserError):
    """A kitchen rule refused the action. The kitchen screen shows it as a notification."""


class KitchenAccessMixin(models.AbstractModel):
    _name = "pos.kitchen.access.mixin"
    _description = "Kitchen RPC access helpers"

    @api.model
    def _kitchen_get_actor(self, actor_chef_id):
        Chef = self.env["pos.kitchen.chef"]
        chef = Chef
        if actor_chef_id:
            chef = Chef.browse(int(actor_chef_id)).exists()
            if not chef or not chef.active:
                raise AccessError(_("This chef is inactive."))
            if chef.company_id not in self.env.companies:
                raise AccessError(_("This chef belongs to another company."))
        return chef

    @api.model
    def _kitchen_is_manager(self):
        """Point of Sale managers (and administrators) see and control the whole kitchen."""
        return self.env.su or self.env.user.has_group("point_of_sale.group_pos_manager")

    @api.model
    def _kitchen_user_chef(self):
        """Chef linked to the current user (through the employee), if any."""
        return self.env["pos.kitchen.chef"].search([
            ("user_id", "=", self.env.uid), ("active", "=", True),
            ("company_id", "in", self.env.companies.ids)], limit=1)

    @api.model
    def _kitchen_check_manager(self, message=None):
        if not self._kitchen_is_manager():
            raise AccessError(message or _("Only kitchen managers can do this."))

    @api.model
    def _kitchen_check_flag(self, config):
        if not config.kitchen_advanced:
            raise UserError(_("Advanced Kitchen is not enabled for this Point of Sale."))
