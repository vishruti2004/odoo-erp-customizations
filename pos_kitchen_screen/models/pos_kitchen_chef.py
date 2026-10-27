from datetime import timedelta, timezone
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .kitchen_mixin import KitchenRuleError

class PosKitchenChef(models.Model):
    _name = "pos.kitchen.chef"
    _description = "Kitchen Chef"
    _inherit = ["pos.load.mixin", "pos.kitchen.access.mixin"]
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

    def _kitchen_on_shift(self, moment=None):
        start = (moment or fields.Datetime.now()).replace(tzinfo=timezone.utc)
        end = start + timedelta(minutes=1)
        working = set()
        chefs = self.sudo().filtered("employee_id")
        for calendar, group in chefs.grouped(lambda chef: chef.employee_id.resource_calendar_id).items():
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
        off = self.filtered(lambda chef: chef.id not in self._kitchen_on_shift())
        if off:
            raise KitchenRuleError(_(
                "%s is not on shift.",
                ", ".join(off.mapped("name"))))

    @api.model
    def get_chefs_on_shift(self, chef_ids=None):
        domain = [("active", "=", True)]
        if chef_ids:
            domain.append(("id", "in", [int(chef_id) for chef_id in chef_ids]))
        return sorted(self.search(domain)._kitchen_on_shift())

    @api.model
    def get_kitchen_access(self, display_id=False):
        admin = self._kitchen_is_admin()
        display = self.env["pos.prep.display"].browse(int(display_id)) if display_id else None
        chef = self._kitchen_user_chef(display.company_id if display else None)
        return {
            "admin": admin,
            "chef": {"id": chef.id, "name": chef.name, "station_ids": chef.station_ids.ids} if chef else False,
        }

    def _kitchen_pending_load(self):
        Station = self.env["pos.kitchen.station"]
        load = {chef.id: {"minutes": 0.0, "items": 0.0} for chef in self}
        if not self:
            return load
        states = self.env["pos.prep.state"].sudo().search(
            Station._kitchen_pending_state_domain() + [("prep_line_id.assigned_chef_id", "in", self.ids)])
        for line in states.prep_line_id:
            qty = line.quantity - line.cancelled
            if qty <= 0 or line.pos_order_line_id.combo_line_ids or line.assigned_chef_id.id not in load:
                continue
            station = line.station_id or line._kitchen_displays().station_ids[:1]
            entry = load[line.assigned_chef_id.id]
            entry["minutes"] += qty * Station._kitchen_item_minutes(line.product_id, station)
            entry["items"] += qty
        return load

    @api.model
    def get_chef_workload(self, display_id=False):
        domain = [("active", "=", True)]
        if display_id:
            display = self.env["pos.prep.display"].browse(int(display_id))
            domain += [("prep_display_id", "=", display.id), ("company_id", "=", display.company_id.id)]
        stations = self.env["pos.kitchen.station"].search(domain)
        chefs = stations.chef_ids.filtered("active")
        load = chefs._kitchen_pending_load()
        on_shift = chefs._kitchen_on_shift()
        result = []
        for chef in chefs:
            chef_stations = chef.station_ids & stations
            metric = "time" if any(station.workload_metric == "time" for station in chef_stations) else "items"
            result.append({
                "id": chef.id, "name": chef.name, "on_shift": chef.id in on_shift, "metric": metric,
                "minutes": round(load[chef.id]["minutes"], 1), "items": load[chef.id]["items"],
                "station_ids": chef_stations.ids,
            })
        return sorted(result, key=lambda entry: (
            not entry["on_shift"], -(entry["minutes"] if entry["metric"] == "time" else entry["items"]),
            entry["name"] or ""))

    @api.model
    def _load_pos_preparation_data_domain(self, data):
        return [("active", "=", True)]

    @api.model
    def _load_pos_preparation_data_fields(self):
        return ["id", "name", "allowed_station_ids", "allowed_category_ids"]
