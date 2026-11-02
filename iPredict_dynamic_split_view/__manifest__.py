# -*- coding: utf-8 -*-

{
    "name": "Dynamic Split View",
    "version": "19.0.1.0.0",
    "summary": "Display List or Kanban and Form views together in a dynamic split layout.",
    "description": "Dynamic Split View for List and Kanban views with configurable layout, default behavior, record creation, resizing, and form synchronization.",
    "category": "Tools",
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "license": "LGPL-3",
    "depends": [
        "web",
    ],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "iPredict_dynamic_split_view/static/src/**/*",
        ],
    },
    "images": [
        "static/description/icon.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
