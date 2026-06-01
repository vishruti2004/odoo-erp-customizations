# -*- coding: utf-8 -*-
{
    "name": "Website Multi Warehouse",
    "summary": "Website wise warehouse stock visibility and ecommerce warehouse management",

    "description": """
        This module allows configuring dedicated warehouses for multiple websites.

        Features:
        - Multiple website support
        - Dedicated warehouse per website
        - Warehouse-wise stock visibility
        - Website-specific ecommerce stock handling
        - Warehouse-based product visibility
        - Warehouse-specific pricing and costing support
        - Website-based sale order warehouse handling
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Website",
    "version": "19.0.1.0.0",

    "depends": [
        "website",
        "website_sale",
        "stock",
        "sale_management",
        "product",
    ],

    "data": [
        "views/website_views.xml",
    ],

    "assets": {},
    "license": "LGPL-3",
    "sequence": 100,

    "installable": True,
    "application": False,
    "auto_install": False,
}