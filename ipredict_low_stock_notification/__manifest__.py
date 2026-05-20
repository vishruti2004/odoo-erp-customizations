# -*- coding: utf-8 -*-
{
    "name": "Stock Alert Manager",
    "summary": "Low stock notification to stock manager",
    "description": """Low stock notification to stock manager with multi-company support.""",

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Inventory",
    "version": "19.0.1.0.0",
    "depends": ["stock", "project", "purchase", "mail"],

    "data": [
        "data/mail_template.xml",
        "data/cron_data.xml",
        "views/res_config_settings_views.xml",
        "views/stock_report_view.xml",
    ],

    "assets": {},
    "license": "LGPL-3",
    "sequence": 100,

    "installable": True,
    "application": False,
    "auto_install": False,
}