# -*- coding: utf-8 -*-
{
    "name": "Website Selection Combo",
    "summary": "Website product selection combo configuration for customizable combo products",

    "description": """
        This module extends Odoo 19 Website Sale to support configurable
        selection combo products.

        Features:
        - Enable Selection Combo for website products
        - Configure category-wise product selections
        - Support All Products or Selected Products
        - Minimum and Maximum product selection validation
        - Allow multiple product selection
        - Include or exclude selected product prices from the combo price
        - Website popup for customer product selection before adding to cart
        - Dynamic category-wise product loading
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Website/eCommerce",
    "version": "19.0.1.0.0",

    "depends": [
        "website_sale",
        "website",
        "sale",
        "product",
    ],

    "data": [
        "security/ir.model.access.csv",

        "views/product_template_views.xml",
        "views/product_selection_combo_views.xml",
    ],


    "license": "LGPL-3",

    "installable": True,
    "application": False,
    "auto_install": False,
}