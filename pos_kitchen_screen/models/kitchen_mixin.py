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
                raise AccessError(_("This chef is not active."))
            if chef.company_id not in self.env.companies:
                raise AccessError(_("This chef belongs to another company."))
        return chef

    @api.model
    def _kitchen_check_flag(self, config):
        if not config.kitchen_advanced:
            raise UserError(_("The advanced kitchen features are not enabled on this Point of Sale."))
