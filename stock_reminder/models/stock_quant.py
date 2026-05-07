from odoo import models, api

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    def _get_html_table_row(self, cells, is_header=False):
        style = "padding:8px 12px; font-size:13px; border-bottom:1px solid #f0f0f0;"
        if is_header:
            style += "background:#3498db; color:#fff; text-align:left;"

        row_html = "<tr>"
        for cell in cells:
            tag = "th" if is_header else "td"
            row_html += f'<{tag} style="{style}">{cell}</{tag}>'
        row_html += "</tr>"
        return row_html

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

            # --- LOCATION TABLE ---
            location_rows = f"""
                <tr style="background:#eee; font-weight:bold;">
                    <td style="padding:8px 12px; border-bottom:2px solid #ddd;">Location Name</td>
                    <td style="padding:8px 12px; border-bottom:2px solid #ddd;">Current Stock</td>
                </tr>"""
            mail_location_rows = location_rows
            
            for lid, qty in location_qtys.items():
                location = self.env['stock.location'].browse(lid)
                qty_color = "#e74c3c" if qty < min_qty else "#27ae60"
                row = f"""<tr>
                    <td style="padding:8px 12px; border-bottom:1px solid #f0f0f0;">{location.display_name}</td>
                    <td style="padding:8px 12px; color:{qty_color}; font-weight:bold; border-bottom:1px solid #f0f0f0;">{qty} {product.uom_id.name}</td>
                </tr>"""
                location_rows += row
                mail_location_rows += row

            # --- VENDOR TABLE 
            vendor_rows = ""
            if product.seller_ids:
                for seller in product.seller_ids:
                    sym = seller.currency_id.symbol or seller.currency_id.name
                    vendor_rows += self._get_html_table_row([seller.partner_id.name, f"{sym} {seller.price}"])
            else:
                vendor_rows = '<tr><td colspan="2" style="text-align:center; padding:10px; color:#999;">No vendors</td></tr>'

            # --- LAST PURCHASE ORDER
            last_po_line = self.env['purchase.order.line'].sudo().search([
                ('product_id', '=', product.id),
                ('order_id.state', 'in', ['purchase', 'done']),
            ], order='date_approve desc', limit=1)

            po_section = ""
            if last_po_line:
                last_po = last_po_line.order_id
                po_curr = last_po.currency_id.symbol or last_po.currency_id.name
                po_date = last_po.date_approve.strftime('%b %d, %Y') if last_po.date_approve else 'N/A'
                po_section = f"""
                <div style="background:#f5fff8; border-left:4px solid #27ae60; border-radius:6px; padding:15px; margin-bottom:15px;">
                    <h3 style="color:#27ae60; margin:0 0 10px 0;">Last Purchase Order</h3>
                    <table style="width:100%; border-collapse:collapse;">
                        {self._get_html_table_row(["Order Reference", last_po.name])}
                        {self._get_html_table_row(["Vendor", last_po.partner_id.name])}
                        {self._get_html_table_row(["Confirmation Date", po_date])}
                        {self._get_html_table_row(["Quantity", f"{last_po_line.product_uom_qty:.2f} {product.uom_id.name}"])}
                        {self._get_html_table_row(["Unit Price", f"{po_curr} {last_po_line.price_unit:.2f}"])}
                        {self._get_html_table_row(["Total Untaxed", f"{po_curr} {last_po_line.price_subtotal:.2f}"])}
                    </table>
                </div>"""
            else:
                po_section = '<div style="background:#f9f9f9; padding:10px; border-radius:6px; margin-bottom:15px; color:#666;">No previous purchase history.</div>'

            description = f"""
<div style="font-family: Arial, sans-serif; padding: 10px; pointer-events: none;" contenteditable="false">
    <div style="background:#fff5f5; border-left:4px solid #e74c3c; border-radius:6px; padding:15px; margin-bottom:15px;">
        <h2 style="color:#e74c3c; margin:0 0 5px 0;">Product Details: {product.name}</h2>
        <p style="color:#666; font-size:13px; margin-bottom:10px;">
            <b>Alert:</b> Minimum quantity according to config must be <b>{min_qty} {product.uom_id.name}</b>.
        </p>
        <table style="width:100%; border-collapse:collapse; background:#fff; border-radius:4px;">
            {location_rows}
        </table>
    </div>

    <div style="background:#f5f8ff; border-left:4px solid #3498db; border-radius:6px; padding:15px; margin-bottom:15px;">
        <h3 style="color:#3498db; margin:0 0 10px 0;">Vendor Pricing</h3>
        <table style="width:100%; border-collapse:collapse;">
            <thead>{self._get_html_table_row(["Vendor Name", "Unit Price"], is_header=True)}</thead>
            <tbody>{vendor_rows}</tbody>
        </table>
    </div>

    {po_section}
    
</div>"""

            # Create Task
            task = self.env['project.task'].sudo().create({
                'name': f'Stock Alert - {product.name}',
                'project_id': project.id,
                'description': description,
                'user_ids': [(4, admin_user.id)],
            })

            # --- SEND MAIL ---
            template = self.env.ref('stock_reminder.mail_template_stock_alert', raise_if_not_found=False)
            email_to = admin_user.email or admin_user.partner_id.email
            if template and email_to:
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                task_url = f"{base_url}/odoo/project/{project.id}/tasks/{task.id}"
                template.with_context(
                    task_url=task_url,
                    min_qty=min_qty,
                    total_stock=total_stock,
                    location_rows_html=mail_location_rows,
                ).send_mail(product_quant_map[product_id].id, force_send=True, email_values={'email_to': email_to})
