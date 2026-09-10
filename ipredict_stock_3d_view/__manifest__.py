# -*- coding: utf-8 -*-

{
    "name": "Stock 3D View",
    "version": "19.0.1.0.0",
    "summary": "Interactive 3D Warehouse & Inventory Visualization",
    "description": """
Stock 3D View - Warehouse Digital Twin

Features:

- Photorealistic 3D Warehouse Rendering (Racks, Floors, Products)
- Live Stock Occupancy (On-hand vs Capacity)
- Interactive Heatmap (Green to Red fill levels)
- Click to Inspect Rack Details
- Search and Fly-to Location/Product
- First-person Walkthrough Mode
- Configurable Rack Dimensions (Length, Width, Height, Shelves)
    """,
    "category": "Inventory/Inventory",
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "license": "LGPL-3",

    "depends": [
        "base",
        "stock",
        "mail",
        "web",
    ],

    "data": [
        "security/ir.model.access.csv",
        "views/stock_location_views.xml",
        "views/stock_3d_actions.xml",
        "views/stock_3d_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [

            "ipredict_stock_3d_view/static/src/lib/CSS2DRenderer.js",
            "ipredict_stock_3d_view/static/src/js/stock_3d_view.js",
            "ipredict_stock_3d_view/static/src/js/slot_grid.js",

            "ipredict_stock_3d_view/static/src/xml/stock_3d_view.xml",
            "ipredict_stock_3d_view/static/src/xml/slot_grid.xml",

            "ipredict_stock_3d_view/static/src/css/stock_3d_view.css",
            "ipredict_stock_3d_view/static/src/css/slot_grid.css",

        ],
    },

    'images': [
        'static/description/icon.png',
    ],

    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}