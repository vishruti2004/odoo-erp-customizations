from datetime import timedelta, timezone

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .kitchen_mixin import KitchenRuleError

class PosKitchenChef(models.Model):
    _name = "pos.kitchen.chef"
    _description = "Kitchen Chef"
    _inherit = ["pos.load.mixin"]
    _order = "name, id"

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", ondelete="cascade", index=True, check_company=True,
        domain="[('company_id', 'in', (company_id, False))]")
    name = fields.Char(related="employee_id.name", store=True, string="Name")
    user_id = fields.Many2one(related="employee_id.user_id", string="User")
    resource_calendar_id = fields.Many2one(
        related="employee_id.resource_calendar_id", string="Working Hours", readonly=False,
        help="The shifts of the chef. Empty: the chef can work at any time.")
    station_ids = fields.Many2many(
        "pos.kitchen.station", string="Kitchen Stations", help="Kitchen stations this chef works on.")
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    category_ids = fields.Many2many(
        "pos.category", string="Categories", compute="_compute_category_ids", store=True, readonly=False,
        help="Product categories this chef prepares. Filled from the selected stations, can be reduced.")
    available_category_ids = fields.Many2many(
        "pos.category", relation="pos_kitchen_chef_available_categ_rel", compute="_compute_available_category_ids")
    on_shift = fields.Boolean("On shift now", compute="_compute_on_shift")
    allowed_station_ids = fields.Json(compute="_compute_allowed_station_ids")
    allowed_category_ids = fields.Json(compute="_compute_allowed_category_ids")

    _employee_uniq = models.Constraint("UNIQUE(employee_id)", "This employee is already a chef.")

    @api.depends("station_ids.category_ids")
    def _compute_available_category_ids(self):
        for chef in self:
            chef.available_category_ids = chef.station_ids.category_ids

    @api.depends("station_ids")
    def _compute_category_ids(self):
        for chef in self:
            chef.category_ids = chef.station_ids.category_ids

    @api.depends("category_ids")
    def _compute_allowed_category_ids(self):
        for chef in self:
            chef.allowed_category_ids = chef.category_ids.ids

    @api.depends("station_ids")
    def _compute_allowed_station_ids(self):
        for chef in self:
            chef.allowed_station_ids = chef.station_ids.ids

    def _kitchen_can_cook(self, product):
        self.ensure_one()
        return not self.category_ids or bool(self.category_ids & product.pos_categ_ids)

    @api.depends("employee_id")
    def _compute_on_shift(self):
        working = self._kitchen_on_shift()
        for chef in self:
            chef.on_shift = chef.id in working

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        if self.employee_id.company_id:
            self.company_id = self.employee_id.company_id

    @api.constrains("employee_id")
    def _check_employee(self):
        if any(not chef.employee_id for chef in self):
            raise ValidationError(_("Please select the employee of the chef."))

    @api.constrains("station_ids", "company_id")
    def _check_station_company(self):
        for chef in self:
            if chef.station_ids.company_id - chef.company_id:
                raise ValidationError(_("A chef can only work on stations belonging to the same company."))

    #  shifts
    def _kitchen_on_shift(self, moment=None):
        start = (moment or fields.Datetime.now()).replace(tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        working = set()
        chefs = self.sudo().filtered("employee_id")
        for calendar, group in chefs.grouped(lambda c: c.employee_id.resource_calendar_id).items():
            if not calendar or calendar.flexible_hours:
                working.update(group.ids)
                continue
            resources = group.employee_id.resource_id
            intervals = calendar._work_intervals_batch(start, end, resources=resources)
            for chef in group:
                if intervals.get(chef.employee_id.resource_id.id):
                    working.add(chef.id)
        return working

    def _kitchen_check_on_shift(self):
        off = self.filtered(lambda c: c.id not in self._kitchen_on_shift())
        if off:
            raise KitchenRuleError(_(
                "%s is not on shift now. Only the chefs working at this time can take items.",
                ", ".join(off.mapped("name"))))

    @api.model
    def get_chefs_on_shift(self, chef_ids=None):
        domain = [("active", "=", True)]
        if chef_ids:
            domain.append(("id", "in", [int(i) for i in chef_ids]))
        return sorted(self.search(domain)._kitchen_on_shift())

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [("active", "=", True)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ["id", "name", "allowed_station_ids", "allowed_category_ids"]
