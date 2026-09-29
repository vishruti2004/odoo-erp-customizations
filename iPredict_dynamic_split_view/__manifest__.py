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
        # Shared state / helpers
        "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_state.js",
        "iPredict_dynamic_split_view/static/src/js/utils/split_view_utils.js",

        # List
        "iPredict_dynamic_split_view/static/src/js/views/list/list_controller.js",
        "iPredict_dynamic_split_view/static/src/js/views/list/list_renderer.js",
        "iPredict_dynamic_split_view/static/src/js/views/list/list_action_menu.js",

        # Kanban
        "iPredict_dynamic_split_view/static/src/js/views/kanban/kanban_controller.js",
        "iPredict_dynamic_split_view/static/src/js/views/kanban/kanban_record.js",
        "iPredict_dynamic_split_view/static/src/js/views/kanban/kanban_action_menu.js",


        # Form
        "iPredict_dynamic_split_view/static/src/js/views/form/form_controller.js",

        # Control Panel
        "iPredict_dynamic_split_view/static/src/js/search/control_panel/control_panel.js",

        # Split View
        "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_divider.js",
        "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_container.js",
        "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_layout.js",

        # XML
        "iPredict_dynamic_split_view/static/src/xml/search/control_panel/control_panel.xml",
        "iPredict_dynamic_split_view/static/src/xml/views/split_view/split_view_container.xml",
        "iPredict_dynamic_split_view/static/src/xml/layout/layout.xml",

        # Style
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