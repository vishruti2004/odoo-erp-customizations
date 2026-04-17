{
    'name': 'POS Default Customer',
    'version': '1.0',
    'category': 'Sales/Point of Sale',
    'summary': 'POS',
    'depends': ['point_of_sale'],
    "sequence": -100,
    "author": "vishruti malaviya",
    "license": "LGPL-3",
    'data': [

            'views/pos_session_config.xml',
            'views/pos_order.xml',


    ],
   'assets': {
    'point_of_sale._assets_pos': [
        'pos_default_customer/static/src/js/set_login_user.js',
        'pos_default_customer/static/src/js/tickit_screen.js',
        'pos_default_customer/static/src/js/order_receipt.js',
        'pos_default_customer/static/src/js/delivery_boy_userlist_line.js',
        'pos_default_customer/static/src/js/delivery_boy_userlist.js',
        'pos_default_customer/static/src/js/delivery_boy_button.js',
        'pos_default_customer/static/src/js/pos_order_data.js',


        'pos_default_customer/static/src/xml/tickit_screen.xml',
        'pos_default_customer/static/src/xml/order_receipt.xml',
        'pos_default_customer/static/src/xml/delivery_boy_button.xml',
        'pos_default_customer/static/src/xml/delivery_boy_userlist.xml',
        'pos_default_customer/static/src/xml/delivery_boy_userlist_line.xml',


    ],
},
    'installable': True,
    'application': False,
}

