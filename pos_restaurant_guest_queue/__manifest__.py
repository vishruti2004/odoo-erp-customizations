# -*- coding: utf-8 -*-
{
    "name": "POS Restaurant Guest Queue",
    "summary": "Manage guest waiting queue and table assignment in POS Restaurant",

    "description": """
        This module extends Odoo 19 POS Restaurant to manage guest waiting queues.

        Features:
        - Guest waiting list management
        - Party size tracking
        - Queue based guest management
        - Table capacity validation
        - Table assignment workflow
        - Table availability notification
        - Dine In specific functionality
        - Restaurant floor integration
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Point of Sale",
    "version": "19.0.1.0.0",

    "depends": [
        "point_of_sale",
        "pos_restaurant",
    ],

    "data": [
        "security/ir.model.access.csv",
        'data/sequence_data.xml',
        "views/pos_guest_queue_views.xml",
        "views/pos_guest_queue_menu.xml",
        "views/res_config_views.xml",
    ],

    'assets': {
        'point_of_sale._assets_pos': [
            'pos_restaurant_guest_queue/static/src/js/*.js',
            'pos_restaurant_guest_queue/static/src/xml/*.xml',
            'pos_restaurant_guest_queue/static/src/css/guest_queue.css',
        ],
},

    "license": "LGPL-3",

    "installable": True,
    "application": False,
    "auto_install": False,
}