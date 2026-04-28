from odoo import fields, models

class InventoryLocationReport(models.Model):
    _name = 'inventory.location.report'
    _description = 'Inventory Location Report'
    _auto = False

    product_id = fields.Many2one('product.product', string='Product', readonly=True)
    categ_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    location_id = fields.Many2one('stock.location', string='Location', readonly=True)
    lot_id = fields.Many2one('stock.lot', string='Lot/Serial Number', readonly=True)
    storage_category_id = fields.Many2one('stock.storage.category', string='Storage Category', readonly=True)
    quantity = fields.Float(string='Quantity', readonly=True)
    reserved_quantity = fields.Float(string='Reserved Quantity', readonly=True)
    available_quantity = fields.Float(string='Available Quantity', readonly=True)
    inventory_quantity = fields.Float(string='Inventoried Quantity', readonly=True)
    inventory_diff_quantity = fields.Float(string='Difference', readonly=True)
    counted = fields.Float(string='Counted', readonly=True)
    inventory_frequency = fields.Integer(string='Inventory Frequency', readonly=True)
    value = fields.Monetary(string='Value', readonly=True, currency_field='currency_id')
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    in_date = fields.Datetime(string='Incoming Date', readonly=True)
    owner_id = fields.Many2one('res.partner', string='Owner', readonly=True)
    package_id = fields.Many2one('stock.package', string='Package', readonly=True)
    product_tmpl_id = fields.Many2one('product.template', string='Product Template', readonly=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', readonly=True)
    user_id = fields.Many2one('res.users', string='Assigned To', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    create_uid = fields.Many2one('res.users', string='Created by', readonly=True)
    create_date = fields.Datetime(string='Created on', readonly=True)
    write_uid = fields.Many2one('res.users', string='Last Updated by', readonly=True)
    write_date = fields.Datetime(string='Last Updated on', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='Unit', readonly=True)
    cyclic_inventory_frequency = fields.Integer(string='Inventory Frequency', readonly=True)
    inventory_quantity_set = fields.Boolean(string='Inventory Quantity Set', readonly=True)
    is_favorite = fields.Boolean(string='Favorite', readonly=True)
    inventory_date = fields.Date(string='Scheduled', readonly=True)
    tracking = fields.Selection([
        ('serial', 'By Unique Serial Number'),
        ('lot', 'By Lots'),
        ('none', 'No Tracking'),
    ], string='Tracking', readonly=True)

    @property
    def _table_query(self):
        return """
            SELECT
                sq.id AS id,
                sq.product_id AS product_id,
                pt.categ_id AS categ_id,
                sq.location_id AS location_id,
                sq.lot_id AS lot_id,
                sl.storage_category_id AS storage_category_id,
                sq.quantity AS quantity,
                sq.reserved_quantity AS reserved_quantity,
                (sq.quantity - sq.reserved_quantity) AS available_quantity,
                sq.inventory_quantity AS inventory_quantity,
                (sq.inventory_quantity - sq.quantity) AS inventory_diff_quantity,
                sq.inventory_quantity AS counted,
                sl.cyclic_inventory_frequency AS inventory_frequency,
                (sq.quantity * COALESCE((pp.standard_price->>sq.company_id::text)::numeric, (pp.standard_price->>'0')::numeric, 0)) AS value,
                sq.company_id AS company_id,
                sq.in_date AS in_date,
                sq.owner_id AS owner_id,
                sq.package_id AS package_id,
                pp.product_tmpl_id AS product_tmpl_id,
                sl.warehouse_id AS warehouse_id,
                sq.user_id AS user_id,
                rc.id AS currency_id,
                sq.create_uid AS create_uid,
                sq.create_date AS create_date,
                sq.write_uid AS write_uid,
                sq.write_date AS write_date,
                pt.uom_id AS uom_id,
                pt.is_favorite AS is_favorite,
                pt.tracking AS tracking,
                sl.cyclic_inventory_frequency AS cyclic_inventory_frequency,
                sq.inventory_quantity_set AS inventory_quantity_set,
                sq.inventory_date AS inventory_date
            FROM stock_quant sq
            JOIN stock_location sl ON sl.id = sq.location_id
            LEFT JOIN product_product pp ON pp.id = sq.product_id
            LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
            LEFT JOIN res_company rc ON rc.id = sq.company_id
            WHERE sl.active = true
        """