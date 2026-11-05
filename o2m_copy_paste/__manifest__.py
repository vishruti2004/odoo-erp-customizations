# -*- coding: utf-8 -*-
{
    "name": "One2Many Copy Paste",
    "summary": "Copy and paste One2many lines between records (Ctrl+C / Ctrl+V).",
    "description": """
Generic One2many line copy & paste for every form view.

- Checkbox column on every One2many list
  (sale order lines, purchase order lines, invoice lines, ...).
- Tick lines, press Ctrl+C  -> "N lines copied".
- Open another record, press Ctrl+V -> lines are added.

    """,
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "support":"ipredictitsolutions@gmail.com",

    "category": "Tools",
    "version": "19.0.1.0.0",
    "depends": ["web", "base_setup"],

    "data": [    
        "views/res_config_settings_views.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "o2m_copy_paste/static/src/utils/line_serializer.js",
            "o2m_copy_paste/static/src/utils/compatibility.js",
            "o2m_copy_paste/static/src/services/clipboard_service.js",
            "o2m_copy_paste/static/src/keyboard/keyboard_handler.js",
            "o2m_copy_paste/static/src/views/fields/x2many/x2many_field.js",
            "o2m_copy_paste/static/src/views/list/list_renderer.js",
        ],
    },

    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
