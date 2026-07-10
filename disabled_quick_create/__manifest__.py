# -*- coding: utf-8 -*-
{
    "name": "Hide Create & Edit Option",
    "summary": "Hide Create and Create & Edit options for Many2one and Many2many fields",

    "description": """
        This module allows administrators to control the visibility of
        Create and Create & Edit options in Many2one and Many2many fields.

        Features:
        - Enable or disable Create/Edit restriction.
        - Apply restriction globally when no models are selected.
        - Apply restriction only for selected models.
        - Configuration available from Settings.
        - Supports Many2one and Many2many fields across Odoo.
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Tools",
    "version": "19.0.1.0.0",

    "depends": [
        "base",
        "web",
        "project",
    ],

    "data": [
        "views/res_config_settings_views.xml",
    ],

    "assets": {
        'web.assets_backend': [
                'disabled_quick_create/static/src/js/disable_quick_create.js',
            ],
    },

    "license": "LGPL-3",

    "installable": True,
    "application": False,
    "auto_install": False,
}