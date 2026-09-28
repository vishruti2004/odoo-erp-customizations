# -*- coding: utf-8 -*-
{
    'name': "Split View",
    'author': 'Albirru Solutions (Irwan Syah)',
    'maintainer': 'Albirru Solutions',
    'support': '1rw4n.5y4h1919@gmail.com',
    'website': 'https://www.albirru.com/',
    'category': 'Tools',
    'version': '19.0.1.0.1',
    'summary': "Free & open-source split view for Odoo 19: see list/kanban and form side by side, with smart buttons and action menus. By Albirru Solutions.",
    'description': """
        Split View Module for Odoo 19
        =============================

        This module provides a split view functionality that allows users to view
        list/kanban and form views side by side.

        Features:
        ---------
        * Toggle split view mode in list and kanban views
        * Resizable split panel with draggable separator
        * Auto-save when navigating between records
        * Persistent user preferences stored in localStorage
        * Keyboard navigation support with pager
        * Close button to exit split view mode
        * Smart buttons display in split view form
        * Action menus (Print, Export, Delete) support

        Usage:
        ------
        1. Navigate to any list or kanban view
        2. Click the split view button in the control panel (panel icon)
        3. Click on any record to open it in the side panel
        4. Drag the separator to resize panels
        5. Click X button or toggle button to close split view
    """,
    'license': 'LGPL-3',
    'depends': ['base', 'web'],
    'assets': {
        'web.assets_backend': [
            # JavaScript files (order matters)
            'split_view/static/src/js/split_view_components.js',
            'split_view/static/src/js/split_view_renderer_mixin.js',
            'split_view/static/src/js/split_view_controller.js',
            'split_view/static/src/js/split_view_form.js',
            'split_view/static/src/js/split_view_container.js',
            'split_view/static/src/js/list_renderer.js',
            'split_view/static/src/js/kanban_controller.js',
            'split_view/static/src/js/kanban_renderer.js',
            'split_view/static/src/js/control_panel.js',

            # XML templates
            'split_view/static/src/xml/split_view.xml',
            'split_view/static/src/xml/list_renderer.xml',
            'split_view/static/src/xml/kanban_renderer.xml',
            'split_view/static/src/xml/control_panel.xml',

            # SCSS styles
            'split_view/static/src/scss/split_view.scss',
        ],
        # Served when the color_scheme cookie is "dark"
        'web.assets_web_dark': [
            'split_view/static/src/scss/split_view.dark.scss',
        ],
    },
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
