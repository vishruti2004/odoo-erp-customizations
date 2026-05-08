from odoo import models, api


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _check_stock_alert(self):
        min_qty = int(self.env['ir.config_parameter'].sudo().get_param('stock_alert.min_qty', 0))
        project = self.env.ref('stock_reminder.project_stock_alerts', raise_if_not_found=False)
        admin_user = self.env.ref('base.user_admin')

        if not min_qty or not project:
            return

        internal_locations = self.env['stock.location'].search([('usage', '=', 'internal')])
        all_quants = self.search([('location_id', 'in', internal_locations.ids)])

        product_location_qty = {}
        product_quant_map = {}

        for quant in all_quants:
            pid = quant.product_id.id
            lid = quant.location_id.id
            if pid not in product_location_qty:
                product_location_qty[pid] = {}
            product_location_qty[pid][lid] = product_location_qty[pid].get(lid, 0) + quant.quantity
            if pid not in product_quant_map:
                product_quant_map[pid] = quant

        for product_id, location_qtys in product_location_qty.items():
            has_low_stock = any(qty < min_qty for qty in location_qtys.values())
            if not has_low_stock:
                continue

            product = self.env['product.product'].browse(product_id)
            total_stock = sum(location_qtys.values())

            existing_task = self.env['project.task'].search([
                ('project_id', '=', project.id),
                ('name', '=', f'Stock Alert - {product.name}'),
            ], limit=1)
            if existing_task:
                continue

            #  Location data - pure Python list of dict
            location_data = []
            for lid, qty in location_qtys.items():
                location = self.env['stock.location'].browse(lid)
                location_data.append({
                    'name': location.display_name,
                    'qty': qty,
                })

            # Last PO data - pure Python dict
            last_po_line = self.env['purchase.order.line'].sudo().search([
                ('product_id', '=', product.id),
                ('order_id.state', 'in', ['purchase', 'done']),
            ], order='date_approve desc', limit=1)

            po_data = False
            if last_po_line:
                last_po = last_po_line.order_id
                sym = last_po.currency_id.symbol or last_po.currency_id.name
                po_data = {
                    'name': last_po.name,
                    'vendor': last_po.partner_id.name,
                    'date': last_po.date_approve.strftime('%b %d, %Y') if last_po.date_approve else 'N/A',
                    'qty': f"{last_po_line.product_uom_qty:.2f} {product.uom_id.name}",
                    'price_unit': f"{sym} {last_po_line.price_unit:.2f}",
                    'total': f"{sym} {last_po_line.price_subtotal:.2f}",
                }

            #  Description 
            description = self.env['ir.qweb']._render(
                'stock_reminder.stock_alert_description_template',
                {
                    'product': product,
                    'min_qty': min_qty,
                    'location_data': location_data,
                    'po_data': po_data,
                }
            )

            #  Task create
            task = self.env['project.task'].sudo().create({
                'name': f'Stock Alert - {product.name}',
                'project_id': project.id,
                'description': description,
                'user_ids': [(4, admin_user.id)],
                'is_stock_alert_task': True,      
                'alert_product_id': product.id,
            })

            template = self.env.ref('stock_reminder.mail_template_stock_alert', raise_if_not_found=False)
            email_to = admin_user.email or admin_user.partner_id.email
            if template and email_to:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                task_url = f"{base_url}/odoo/project/{project.id}/tasks/{task.id}"
                template.with_context(
                    task_url=task_url,
                    min_qty=min_qty,
                    total_stock=total_stock,
                    location_data=location_data,
                ).send_mail(
                    product_quant_map[product_id].id,  # stock.quant id
                    force_send=True,
                    email_values={'email_to': email_to}
                )