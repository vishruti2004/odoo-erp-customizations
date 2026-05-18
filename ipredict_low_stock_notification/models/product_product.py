import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def cron_check_low_stock(self):

        mail_template = self.env.ref(
            'ipredict_low_stock_notification.mail_template_low_stock_notification',
            raise_if_not_found=False
        )

        if not mail_template:
            _logger.error("Low stock mail template not found.")
            return

        companies = self.env['res.company'].search([])

        for company in companies:

            managers = company.low_stock_manager_ids.filtered('partner_id')

            if not managers:
                continue

            products = self.env['product.product'].sudo().search([
                ('type', 'in', ['product', 'consu']),
                '|',
                ('company_id', '=', company.id),
                ('company_id', '=', False),
            ])

            if not products:
                continue

            orderpoints = self.env['stock.warehouse.orderpoint'].sudo().search([
                ('product_id', 'in', products.ids),
                ('company_id', '=', company.id),
                ('active', '=', True),
            ])

            min_qty_map = {
                orderpoint.product_id.id: orderpoint.product_min_qty
                for orderpoint in orderpoints
            }

            low_stock_products = []

            for product in products:

                available_qty = product.with_context(
                    allowed_company_ids=[company.id],
                    company_id=company.id,
                ).qty_available

                minimum_qty = min_qty_map.get(
                    product.id,
                    company.low_stock_min_qty,
                )

                if minimum_qty <= 0 or available_qty > minimum_qty:
                    continue

                low_stock_products.append({
                    'name': product.display_name,
                    'qty_available': available_qty,
                    'min_qty': minimum_qty,
                })

            if not low_stock_products:
                continue

            message_body = (
                "The following products are below minimum stock level:"
                "<br/><br/>"
                + "<br/>".join(
                    f"• {product['name']} "
                    f"(Available: {product['qty_available']} | "
                    f"Minimum: {product['min_qty']})"
                    for product in low_stock_products
                )
            )

            for manager in managers:
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

            mail_template.sudo().with_company(company).with_context({
                'low_stock_products': low_stock_products,
                'allowed_company_ids': [company.id],
                'company_id': company.id,
            }).send_mail(
                company.id,
                email_values={
                    'recipient_ids': [(6, 0, managers.mapped('partner_id').ids)],
                    'email_from': (
                        company.email_formatted
                        or self.env.company.email_formatted
                    ),
                },
                force_send=False,
            )

            _logger.info(
                "Low stock notification sent for company: %s",
                company.name,
            )