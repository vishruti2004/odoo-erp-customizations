from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class KitchenAccessMixin(models.AbstractModel):
    
    _name = "pos.kitchen.access.mixin"
    _description = "Kitchen RPC access helpers"

    @api.model
    def _kitchen_get_actor(self, actor_chef_id, stations=None, strict_station=False):
        """Validate the acting chef and the caller's rights, return the chef (may be empty)."""
        Chef = self.env["pos.kitchen.chef"]
        chef = Chef
        if actor_chef_id:
            chef = Chef.browse(int(actor_chef_id)).exists()
            if not chef or not chef.active:
                raise AccessError(_("This chef is not active."))
            if chef.company_id not in self.env.companies:
                raise AccessError(_("This chef belongs to another company."))
            if strict_station and stations and chef.station_ids and not (chef.station_ids & stations):
                raise AccessError(_("Chef %(chef)s is not allowed to work on this station.", chef=chef.name))
        return chef

    @api.model
    def _kitchen_check_flag(self, config):
        if not config.kitchen_advanced:
            raise UserError(_("The advanced kitchen features are not enabled on this Point of Sale."))
