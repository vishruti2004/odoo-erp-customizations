{
    'name': 'POS Default Customer',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'summary': 'POS',
    'depends': ['point_of_sale'],
    "sequence": -100,
    "author": "vishruti malaviya",
    "license": "LGPL-3",
    'data': [],
   'assets': {
    'point_of_sale._assets_pos': [
        'pos_default_customer/static/src/js/set_login_user.js',
    ],
},
    'installable': True,
    'application': False,
}