# -*- coding: utf-8 -*-
{
    "name": "Gym Management - Base",
    "summary": "Base module for Gym Management System",

    "description": """
        Gym Management Base for Odoo 19.

        Features:
        - Gym Management Root Menu
        - Security Groups and Access Rights
        - Role-based User Permissions
        - Base Configuration
        - Common Settings
        - Foundation for all Gym Management Modules
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Services",
    "version": "19.0.1.0.0",

    "depends": [
        "base",
        "hr",
        "iPredict_locker_management",


    ],

    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",

        # Views
        "views/res_config_settings_views.xml",
        "views/menu_views.xml",

    ],

    'images': [
        'static/description/icon.png',
    ],

    "license": "LGPL-3",

    "installable": True,
    "application": True,
    "auto_install": False,
}