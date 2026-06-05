from odoo import models

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        result = super().button_validate()
        for picking in self:
            if picking.picking_type_code not in ['incoming', 'outgoing']:
                continue
            
            warehouse = picking.picking_type_id.warehouse_id
            if not warehouse:
                continue
            
            for move in picking.move_ids:
                self.env['warehouse.product.price']._update_warehouse_cost(
                    move, warehouse, picking.picking_type_code
                )
        return result