from odoo import api, fields, models

class ProductProduct(models.Model):
    _inherit = 'product.product'

    is_low_stock = fields.Boolean(search='_search_is_low_stock')

    @api.model
    def _search_is_low_stock(self, operator, value):
        if not value:
            return [('id', 'not in', [])]
        
        company_id = self.env.context.get('company_id') or self.env.company.id
        low_stock_ids = self.get_low_stock_product_ids(company_id)
        return [('id', 'in', low_stock_ids)]

    @api.model
    def get_low_stock_product_ids(self, company_id):
        company = self.env['res.company'].sudo().browse(company_id)
        
      
        products = self.env['product.product'].sudo().search([
            ('type', '=', 'consu'),
            ('is_storable', '=', True),
            '|',
            ('company_id', '=', company_id),
            ('company_id', '=', False),
        ])
        
        orderpoints = self.env['stock.warehouse.orderpoint'].sudo().search([
            ('product_id', 'in', products.ids),
            ('company_id', '=', company_id),
            ('active', '=', True),
        ])
        min_qty_map = {op.product_id.id: op.product_min_qty for op in orderpoints}
        
        warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', company_id)], limit=1)
        location_id = warehouse.lot_stock_id.id if warehouse else False
        
        low_stock_ids = []
        for product in products:
            context_data = {
                'allowed_company_ids': [company_id],
                'company_id': company_id,
                'force_company': company_id,
            }
            if location_id:
                context_data['location'] = location_id  
                
            qty = product.with_context(**context_data).qty_available
            min_qty = min_qty_map.get(product.id, company.low_stock_min_qty)
            
            if min_qty <= 0 or qty > min_qty:
                continue
            low_stock_ids.append(product.id)
            
        return low_stock_ids

    @api.model
    def cron_check_low_stock(self):
        mail_template = self.env.ref('ipredict_low_stock_notification.mail_template_low_stock_notification', raise_if_not_found=False)
        if not mail_template:
            return
        
        companies = self.env['res.company'].search([])
        for company in companies:
            managers = company.low_stock_manager_ids.filtered('partner_id')
            if not managers:
                continue
                
            low_stock_ids = self.get_low_stock_product_ids(company.id)
            products = self.browse(low_stock_ids)
            if not products:
                continue
                
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or 'http://localhost:8069'
            report_url = f"{base_url}/low-stock-report?company_id={company.id}"
            
            warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
            location_id = warehouse.lot_stock_id.id if warehouse else False
            context_dict = {'allowed_company_ids': [company.id], 'company_id': company.id, 'force_company': company.id}
            if location_id:
                context_dict['location'] = location_id

            inbox_display_products = products[:5]
            product_list_html = "<ul>"
            for product in inbox_display_products:
                qty = product.with_context(**context_dict).qty_available
                product_list_html += f"<li><b>{product.display_name}</b> (Available: {qty})</li>"          
            
            message_body = (
                f"The following products are below minimum stock level for <b>{company.name}</b>:<br/>"
                f"{product_list_html}<br/>"
                f"Kindly click the button below to view the detailed low stock report.<br/><br/>"
                f"<a href='{report_url}' target='_blank' class='btn btn-primary fw-bold px-3 py-2'>View Low Stock Report</a>"
            )
            
            for manager in managers:
                try:
                    self.env['mail.message'].sudo().with_company(company).create({
                        'message_type': 'user_notification',
                        'subtype_id': self.env.ref('mail.mt_comment').id,
                        'subject': f"[{company.name}] Low Stock Alert",
                        'body': message_body,
                        'notification_ids': [(0, 0, {
                            'res_partner_id': manager.partner_id.id,
                            'notification_type': 'inbox',
                            'is_read': False,
                        })],
                    })
                except Exception:
                    pass
                    
            display_products_records = products[:15]
            remaining = len(products) - 15
            low_stock_products_dict_list = []
            for product in display_products_records:
                qty = product.with_context(**context_dict).qty_available
                orderpoint = product.orderpoint_ids.filtered(lambda op: op.company_id.id == company.id and op.active)[:1]
                minimum_qty = orderpoint.product_min_qty if orderpoint else company.low_stock_min_qty
                
                low_stock_products_dict_list.append({
                    'name': product.display_name,
                    'qty_available': qty,
                    'min_qty': minimum_qty,
                })
                
            try:
                mail_template.sudo().with_company(company).with_context({
                    'low_stock_products': low_stock_products_dict_list,
                    'remaining_count': remaining if remaining > 0 else 0,
                    'allowed_company_ids': [company.id],
                    'company_id': company.id,
                    'base_url': base_url,
                }).send_mail(
                    company.id,
                    email_values={
                        'email_to': False,
                        'recipient_ids': [(6, 0, managers.mapped('partner_id').ids)],
                        'email_from': company.email_formatted or self.env.company.email_formatted,
                    },
                    force_send=False,
                )
            except Exception:
                pass