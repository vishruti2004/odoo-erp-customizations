
# -*- coding: utf-8 -*-
{
    "name": "POS Category Layout Customization",
    "version": "19.0.1.0.0",
    "summary": "Category breadcrumb, Top bar / Horizontal / Sidebar category layouts, product cards, colors and fonts for POS.",
    "description": """
Customize POS category navigation and product display.

- Top Bar Display, Horizontal Category Layout and Sidebar Display.
- Left or Right Sidebar Position.
- Category Sorting by Alphabetical or Sequence.
- Product Card Design: Standard, Compact and Image-Focused.
- Product Grid Columns from 1 to 12.
- Product Card Spacing: Compact, Normal and Spacious.
- Custom Primary, Category and Product Card Colors.
- Font Configuration using Odoo document font options.
    """,
    "category": "Sales/Point of Sale",
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "web"],

    "data": [
        "views/pos_config_views.xml",
    ],

    "assets": {
        "point_of_sale._assets_pos": [
            "pos_category_layout/static/src/components/category_selector.js",
            "pos_category_layout/static/src/components/category_selector.xml",
            "pos_category_layout/static/src/screens/product_screen.js",
            "pos_category_layout/static/src/screens/product_screen.xml",
            "pos_category_layout/static/src/scss/category_layout.scss",
            "pos_category_layout/static/src/scss/product_card.scss",
            "pos_category_layout/static/src/scss/theme.scss",
        ],
    },

    "installable": True,
    "application": False,
    "auto_install": False,
}
