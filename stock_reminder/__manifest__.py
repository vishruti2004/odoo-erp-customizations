{
    'name': 'Stock Alert Manager',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'purchase stock reminder when stock is empty',
    'depends': ['stock', 'project', 'purchase', 'mail'],
    "sequence": -100,
    "author": "vishruti malaviya",
    "license": "LGPL-3",
    'data': [
                'data/project_data.xml',
                'data/cron_data.xml',
                'data/mail_template.xml',

                'views/res_config_settings_views.xml',
                # 'views/description_template.xml',
    ],
    'installable': True,
    'application': False,
}