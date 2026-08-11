# -*- coding: utf-8 -*-

{
    "name": "Locker Management",
    "version": "19.0.1.0.0",
    "summary": "Manage locker allocation, availability, and access.",
    "description": """
Locker Management

Features:

- Locker Profile Management
- Locker Management
- Locker Allocation Management
- Locker Availability Tracking
- Locker Access Method Management
- Locker Status Tracking
- 3D Locker Visualization
    """,
    "category": "Operations",
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "license": "LGPL-3",

    "depends": [
        "base",
        "mail",
        "contacts",
        "product",
        "stock",
        "account",
        "sms",
    ],

    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/mail_template.xml",


        # Views
        "views/locker_profile_views.xml",
        "views/locker_locker_views.xml",
        "views/locker_allocation_views.xml",
        "views/res_partner_views.xml",
        "views/locker_location_views.xml",
        "views/res_company_views.xml",
        "views/locker_access_views.xml",
        "views/locker_access_credential_views.xml",

        # Menus
        "views/locker_menus.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "iPredict_locker_management/static/src/lib/jsQR.js",

            "iPredict_locker_management/static/src/lib/three.module.js",
            "iPredict_locker_management/static/src/lib/three.core.js",
            "iPredict_locker_management/static/src/lib/CSS2DRenderer.js",

            "iPredict_locker_management/static/src/js/locker_3d_view.js",
            "iPredict_locker_management/static/src/xml/locker_3d_view.xml",
            "iPredict_locker_management/static/src/css/locker_3d_view.css",

            "iPredict_locker_management/static/src/js/locker_kiosk.js",
            "iPredict_locker_management/static/src/xml/locker_kiosk.xml",
            "iPredict_locker_management/static/src/css/locker_kiosk.css",
        ],
    },

    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}