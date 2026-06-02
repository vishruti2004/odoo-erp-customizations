from odoo import fields, models


class WarehouseProductPrice(models.Model):
    _name = 'warehouse.product.price'
    _description = 'Warehouse Product Cost'

    product_id = fields.Many2one('product.template', string='Product')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    cost = fields.Float(string='Cost')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    warehouse_price_ids = fields.One2many(
        'warehouse.product.price',
        'product_id',
        string='Warehouse Cost'
    )


# class StockLandedCost(models.Model):
#     _inherit = 'stock.landed.cost'

#     def button_validate(self):
#         result = super().button_validate()

#         for landed_cost in self:
#             #  all transfers linked to this landed cost
#             for stock_picking in landed_cost.picking_ids:
#                 # Get the warehouse from the destination location
#                 warehouse = stock_picking.location_dest_id.warehouse_id
#                 if not warehouse:
#                     continue

#                 # all product movements in the transfer
#                 for stock_move in stock_picking.move_ids:
#                     product_template = stock_move.product_id.product_tmpl_id
#                     # Get updated standard price after landed cost validation
#                     warehouse_cost = stock_move.product_id.standard_price

#                     # Check if a record already exists for this product and warehouse
#                     price_record = self.env['warehouse.product.price'].search([
#                         ('product_id', '=', product_template.id),
#                         ('warehouse_id', '=', warehouse.id),
#                     ], limit=1)

#                     if price_record:
#                         # Update existing record
#                         price_record.cost = warehouse_cost
#                     else:
#                         # Create new record
#                         self.env['warehouse.product.price'].create({
#                             'product_id': product_template.id,
#                             'warehouse_id': warehouse.id,
#                             'cost': warehouse_cost,
#                         })

#         return result

# class StockLandedCost(models.Model):
#     _inherit = 'stock.landed.cost'

#     def button_validate(self):
#         result = super().button_validate()

#         for landed_cost in self:
#             # all transfers linked to this landed cost
#             for stock_picking in landed_cost.picking_ids:
                
#                 #  Destination location mathi warehouse tracking
#                 warehouse = stock_picking.location_dest_id.warehouse_id
                
#                 # Jo na male to Operation Type (Receipts) par thi warehouse pick karo
#                 if not warehouse and stock_picking.picking_type_id.warehouse_id:
#                     warehouse = stock_picking.picking_type_id.warehouse_id

#                 # Still safety checkpoint
#                 if not warehouse:
#                     continue

#                 # all product movements in the transfer
#                 for stock_move in stock_picking.move_ids:
#                     product_template = stock_move.product_id.product_tmpl_id
                    
#                     warehouse_cost = stock_move.product_id.standard_price

                  
#                     self.env['warehouse.product.price'].create({
#                         'product_id': product_template.id,
#                         'warehouse_id': warehouse.id,
#                         'cost': warehouse_cost,
#                     })

#         return result


class StockLandedCost(models.Model):
    _inherit = 'stock.landed.cost'

    def button_validate(self):
        result = super().button_validate()

        for landed_cost in self:
            for stock_picking in landed_cost.picking_ids:
                warehouse = stock_picking.location_dest_id.warehouse_id
                if not warehouse and stock_picking.picking_type_id.warehouse_id:
                    warehouse = stock_picking.picking_type_id.warehouse_id

                if not warehouse:
                    continue

                for stock_move in stock_picking.move_ids:
                    product_template = stock_move.product_id.product_tmpl_id
                    warehouse_cost = stock_move.product_id.standard_price

                    price_record = self.env['warehouse.product.price'].search([
                        ('product_id', '=', product_template.id),
                        ('warehouse_id', '=', warehouse.id),
                    ], limit=1)

                    if price_record:
                        price_record.cost = warehouse_cost
                    else:
                        self.env['warehouse.product.price'].create({
                            'product_id': product_template.id,
                            'warehouse_id': warehouse.id,
                            'cost': warehouse_cost,
                        })

        return result