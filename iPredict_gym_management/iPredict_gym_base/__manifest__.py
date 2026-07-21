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
    ],

    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",

        # Views
        "views/menu_views.xml",
    ],

    "license": "LGPL-3",

    "installable": True,
    "application": True,
    "auto_install": False,
}