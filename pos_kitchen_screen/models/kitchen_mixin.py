from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class KitchenRuleError(UserError):
    pass


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
    def _kitchen_is_admin(self):
        return self.env.su or self.env.user.has_group("base.group_system")

    @api.model
    def _kitchen_user_chef(self, company=None):
        company = company or self.env.company
        return self.env["pos.kitchen.chef"].search([
            ("user_id", "=", self.env.uid), ("active", "=", True), ("company_id", "=", company.id)], limit=1)

    @api.model
    def _kitchen_check_admin(self, message=None):
        if not self._kitchen_is_admin():
            raise AccessError(message or _("Only administrators can do this."))

    @api.model
    def _kitchen_check_flag(self, config):
        if not config.kitchen_advanced:
            raise UserError(_("Advanced Kitchen is not enabled for this Point of Sale."))
