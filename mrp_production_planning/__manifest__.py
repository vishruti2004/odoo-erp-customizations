# -*- coding: utf-8 -*-
{
    "name": "MRP Production Planning - Phase Wise Material Check",
    "summary": "Phase-wise material availability checking for Manufacturing Orders",

    "description": """
        This module extends Odoo 19 Manufacturing to support phase-wise material
        availability checking.

        Features:
        - Phase-wise material availability checking before each Work Order starts
        - Auto RFQ creation on material shortage
        - Purchase department notification on shortage
        - Expected material arrival date tracking
        - Deferred material reservation (phase-wise, not full BOM at confirmation)
        - Material scheduled based on operation dates, not MO start date
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Manufacturing",
    "version": "19.0.1.0.0",

    "depends": [
    "mrp",
    "stock",
    "purchase",
    "mail",
    "product",
],

    "data": [
         'security/ir.model.access.csv',

        "data/cron_data.xml",
        "data/mail_template.xml",

        "views/res_config_settings_views.xml",
    ],

    "license": "LGPL-3",

    "installable": True,
    "application": False,
    "auto_install": False,
}