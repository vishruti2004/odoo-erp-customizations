# -*- coding: utf-8 -*-
{
    "name": "One2Many Copy Paste",
    "version": "19.0.1.0.0",
    "summary": "Copy and paste One2many lines between records (Ctrl+C / Ctrl+V).",
    "description": """
Generic One2many line copy & paste for every form view.

- Checkbox column on every One2many list
  (sale order lines, purchase order lines, invoice lines, ...).
- Tick lines, press Ctrl+C  -> "N lines copied".
- Open another record, press Ctrl+V -> lines are added (onchange is applied).
- Clipboard survives page refresh (localStorage).
- Standalone list views and Many2many fields are NOT touched.
    """,
    "category": "Tools",
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "license": "LGPL-3",
    "depends": ["web"],

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
    "installable": True,
    "application": False,
    "auto_install": False,
}
