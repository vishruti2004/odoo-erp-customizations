# # -*- coding: utf-8 -*-
# from odoo import models

# class MrpProduction(models.Model):
#     _inherit = "mrp.production"

#     def action_confirm(self):
#         result = super().action_confirm()
#         for production in self:
#             raw_moves = production.move_raw_ids.filtered(lambda move: move.state not in ("done", "cancel"))
#             if raw_moves:
#                 raw_moves._do_unreserve()
#             for move in raw_moves:
#                 move._set_quantity_done(0)
#                 move.picked = False
#         return result

# -*- coding: utf-8 -*-
from odoo import models

class MrpProduction(models.Model):
    _inherit = "mrp.production"

    def action_confirm(self):
        result = super().action_confirm()
        
        for production in self:
            # 1. Check if phase-wise material check enabled
            if not production.company_id.phase_wise_material_check:
                continue
            
            # 2. Link components with workorders
            if production.workorder_ids:
                for workorder in production.workorder_ids:
                    workorder._set_phase_components()
                        
            # 3. Unreserve all components
            raw_moves = production.move_raw_ids.filtered(
                lambda move: move.state not in ("done", "cancel")
            )
            raw_moves._do_unreserve()
            
            # 4. Reset quantity and picked flag
            for move in raw_moves:
                move._set_quantity_done(0)
                move.picked = False
        
        return result