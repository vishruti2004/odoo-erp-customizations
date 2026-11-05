{
    'name': 'Non-Moving Stock Report',
    'summary': 'Find products with available stock and no customer delivery for a chosen number of days',
    'description': '''
Non-Moving Stock Report
=======================
Lists products and lots/serial numbers with positive available quantity in
internal locations that had no completed customer delivery during the number
of days entered in the wizard. Products with no delivery history use the date
the stock was received.
    ''',

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "support":"ipredictitsolutions@gmail.com",

    'category': 'Inventory/Reporting',
    'version': '19.0.1.0.0',
    'depends': ['stock_account', 'sale_stock'],

    'data': [
        'security/ir.model.access.csv',
        'security/non_moving_stock_rules.xml',
        'wizard/non_moving_stock_wizard_views.xml',
        'views/non_moving_stock_views.xml',
    ],
    
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}