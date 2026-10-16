# -*- coding: utf-8 -*-
{
    "name": "POS Category Layout Customization",
    "version": "19.0.2.4.0",
    "summary": "Configurable POS category layouts (top bar, sidebar, popup), card styles, search, pagination and font.",
    "description": """
        Customize the POS category navigation, per Point of Sale.

        - Layout: Top Bar, Sidebar (left / right, collapsible) or Popup.
        - Card styles: normal or cover image, image position, categories per row.
        - Scrollbar (vertical / horizontal) or carousel for the top bar.
        - Nested list in the sidebar, breadcrumb, sorting, product count, category colors.
        - Category search bar and an "All categories" popup.
        - Font family for the category area.
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
            "pos_category_layout/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
