# -*- coding: utf-8 -*-

{
    "name": "Dynamic Split View",
    "version": "19.0.1.0.0",
    "summary": "Display List or Kanban and Form views together in a dynamic split layout.",
    "description": """
Dynamic Split View

Features:

- List + Form Split View
- Kanban + Form Split View
- Separate List Split View Configuration
- Separate Kanban Split View Configuration
- Horizontal Split Direction
- Vertical Split Direction
- Resizable Split Panels
- Collapse / Expand Form Panel
- Selected Record in Form Panel
- Create New Record in Split View
- List/Kanban and Form Synchronization
- Search, Filter and Group By Support
- Pagination Support
- Native Form Operations
- Chatter and Activities Support
- Smart Buttons and Wizards Support
- Split View State Persistence
- Record Navigation Support
- Action-based Split View
    """,
    "category": "Tools",
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "license": "LGPL-3",

    "depends": [
        "base",
        "web",
    ],

    "data": [
        # Views
        "views/res_config_settings_views.xml",
    ],

   "assets": {
    "web.assets_backend": [
        "iPredict_dynamic_split_view/static/src/js/split_view_state.js",
        "iPredict_dynamic_split_view/static/src/js/split_view_container.js",
        "iPredict_dynamic_split_view/static/src/js/split_view_divider.js",

        "iPredict_dynamic_split_view/static/src/js/list_split_view.js",
        "iPredict_dynamic_split_view/static/src/js/kanban_split_view.js",
        "iPredict_dynamic_split_view/static/src/js/split_view_control_panel.js",
        "iPredict_dynamic_split_view/static/src/js/split_view_layout.js",  
        "iPredict_dynamic_split_view/static/src/js/split_view_form_layout.js",  


        "iPredict_dynamic_split_view/static/src/xml/split_view_buttons.xml",
        "iPredict_dynamic_split_view/static/src/xml/split_view_container.xml",
        "iPredict_dynamic_split_view/static/src/xml/split_view_layout.xml", 

        "iPredict_dynamic_split_view/static/src/scss/split_view.scss",
    ],
},
    "images": [
        "static/description/icon.png",
    ],

    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}