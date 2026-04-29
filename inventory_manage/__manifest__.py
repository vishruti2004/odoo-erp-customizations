{
    'name': 'Inventory Manage',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'inventory',
    'author': 'Vishruti Malaviya',
    'depends': ['stock','sale'],
    'data': [

        'security/ir.model.access.csv',

        'data/stock_location.xml',

        'views/sale_order_line_views.xml',
        'views/purchase_views.xml',
        'views/inventory_location_report_views.xml',
        'views/pricelist_discount_views.xml',


        
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}