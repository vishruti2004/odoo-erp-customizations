from odoo import models, api

class StockLocation(models.Model):
    _inherit = 'stock.location'

    @api.model
    def _create_shelf_hierarchy(self):
        # find parent stock
        parent_stock = self.env.ref('stock.stock_location_stock')

        # 2. shelf create or find
        shelf1 = self.search([('name', '=', 'Shelf 1'), ('location_id', '=', parent_stock.id)], limit=1)
        if not shelf1:
            shelf1 = self.create({
                'name': 'Shelf 1',
                'location_id': parent_stock.id,
                'usage': 'internal'
            })

        # section A b c create
        for char in ['A', 'B', 'C']:
            section = self.search([('name', '=', char), ('location_id', '=', shelf1.id)], limit=1)
            if not section:
                section = self.create({
                    'name': char,
                    'location_id': shelf1.id,
                    'usage': 'internal'
                })
            
            # row 1 to 5 and column 1 to 5
            for r in range(1, 6):
                for c in range(1, 6):
                    loc_name = f"R{r}C{c}"
                    exists = self.search([('name', '=', loc_name), ('location_id', '=', section.id)], limit=1)
                    if not exists:
                        self.create({
                            'name': loc_name,
                            'location_id': section.id,
                            'usage': 'internal'
                        })

    @api.depends('complete_name', 'usage')
    def _compute_display_name(self):
        super()._compute_display_name()
        if not self.env.context.get('show_location_qty'):
            return
        product_id = self.env.context.get('product_id')
        for location in self:
            if location.usage == 'internal':
                domain = [
                    ('location_id', '=', location.id),
                    ('quantity', '>', 0),
                ]
                if product_id:
                    domain.append(('product_id', '=', product_id))
                quants = self.env['stock.quant'].search(domain)
                available_qty = sum(quants.mapped('available_quantity'))
                location.display_name = f"[{available_qty:.1f}] {location.display_name}"

  