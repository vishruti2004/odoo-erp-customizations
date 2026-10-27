{
    "name": "POS Restaurant Kitchen Screen",
    "version": "19.0.1.1.7",
    "category": "Sales/Point of Sale",
    "summary": "Station routing, priority, chef shifts"
               "kitchen performance report, workload balancing "
               "and automatic station / chef assignment for the Odoo 19 kitchen display",
    "author": "Custom",
    "depends": ["point_of_sale", "pos_enterprise", "hr"],
    "data": [
        "security/kitchen_security.xml",
        "security/ir.model.access.csv",
        "views/kitchen_station_views.xml",
        "views/kitchen_chef_views.xml",
        "views/product_template_views.xml",
        "views/res_config_settings_views.xml",
        "views/kitchen_performance_views.xml",
        "views/kitchen_menus.xml",
    ],
    "assets": {
        "pos_preparation_display.assets": [
            "pos_kitchen_screen/static/src/app/**/*",
        ],
        "point_of_sale._assets_pos": [
            "pos_kitchen_screen/static/src/override/point_of_sale/**/*",
        ],
        "web.assets_backend": [
            "pos_kitchen_screen/static/src/backend/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "OPL-1",
}
