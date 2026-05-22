# -*- coding: utf-8 -*-
{
    "name": "MRP Custom Serial Generation",
    "summary": "Product-wise custom serial number generation in Manufacturing Orders",
    "description": """
        Adds a checkbox in Manufacturing Order to enable custom serial number generation.
        When enabled, user can select a prefix from dropdown and serial numbers are
        generated product-wise with sequential numbering starting from 0001.
        Default behaviour is fully preserved when checkbox is unchecked.
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Manufacturing",
    "version": "19.0.1.0.0",
    "depends": ["mrp", "stock"],

    "data": [
        "views/mrp_production_views.xml",
        "views/product_product.xml",
    ],

    "assets": {},
    "license": "LGPL-3",
    "sequence": 100,

    "installable": True,
    "application": False,
    "auto_install": False,
}