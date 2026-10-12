# -*- coding: utf-8 -*-
{
    "name": "POS Category Layout Customization",
    "version": "19.0.2.0.0",
    "summary": "Configurable POS category layouts (top bar, sidebar, grid cards, list, nested tree), product sorting, price / description, colors and fonts.",
    "description": """
Customize POS category navigation and product display, per Point of Sale.

Category layout
- Top Bar or Sidebar (left / right, collapsible).
- Display style: Grid cards, List or Nested (expand / collapse tree).
- Category content: image + name, name only or image only.
- Breadcrumb navigation, category sorting, product count per category.

Product display
- Products per row, product sorting (new arrivals, name, price).
- Show product price and description, product list view.
- Product card color and font family.
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
            "pos_category_layout/static/src/utils/font_loader.js",
            "pos_category_layout/static/src/services/pos_store.js",
            "pos_category_layout/static/src/components/product_card.js",
            "pos_category_layout/static/src/components/product_card.xml",
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
