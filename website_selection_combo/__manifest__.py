{
    "name": "Website Selection Combo",
    "summary": "Website product selection combo configuration for customizable combo products",
    "description": """
        This module extends Odoo 19 Website Sale to support configurable
        selection combo products.
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
        "views/cart_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "website_selection_combo/static/src/js/product_card.js",
            "website_selection_combo/static/src/js/combo_configurator_dialog.js",
            "website_selection_combo/static/src/js/cart_service.js",
            "website_selection_combo/static/src/js/cart_edit_combo.js",
            "website_selection_combo/static/src/xml/product_card.xml",
            "website_selection_combo/static/src/xml/combo_configurator_dialog.xml",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}