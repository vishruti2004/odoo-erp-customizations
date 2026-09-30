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
        "base",
        "web",
    ],

    "data": [
        "views/res_config_settings_views.xml",
    ],

    "assets": {
        "web.assets_backend": [
            "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_state.js",
            "iPredict_dynamic_split_view/static/src/js/utils/split_view_utils.js",

            "iPredict_dynamic_split_view/static/src/js/views/list/list_controller.js",
            "iPredict_dynamic_split_view/static/src/js/views/list/list_renderer.js",
            "iPredict_dynamic_split_view/static/src/js/views/list/list_action_menu.js",

            "iPredict_dynamic_split_view/static/src/js/views/kanban/kanban_controller.js",
            "iPredict_dynamic_split_view/static/src/js/views/kanban/kanban_record.js",
            "iPredict_dynamic_split_view/static/src/js/views/kanban/kanban_action_menu.js",

            "iPredict_dynamic_split_view/static/src/js/views/form/form_controller.js",

            "iPredict_dynamic_split_view/static/src/js/search/control_panel/control_panel.js",

            "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_divider.js",
            "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_container.js",
            "iPredict_dynamic_split_view/static/src/js/views/split_view/split_view_layout.js",

            "iPredict_dynamic_split_view/static/src/xml/search/control_panel/control_panel.xml",
            "iPredict_dynamic_split_view/static/src/xml/views/split_view/split_view_container.xml",
            "iPredict_dynamic_split_view/static/src/xml/layout/layout.xml",

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