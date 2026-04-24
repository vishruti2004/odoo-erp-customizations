{
    'name': 'Inventory Manage',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'inventory',
    'author': 'Vishruti Malaviya',
    'depends': ['stock','sale'],
    'data': [
        'data/stock_location.xml',

        'views/sale_order_line_views.xml',


        
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}