{
    'name': 'Stock Alert Manager',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'low stock notification to stock manager',
    'depends': ['stock', 'project', 'purchase', 'mail'],
    "sequence": -100,
    "author": "vishruti malaviya",
    "license": "LGPL-3",
    'data': [
                # 'data/cron_data.xml',
                # 'data/mail_template.xml',

                'views/res_config_settings_views.xml',
                

    ],
    'installable': True,
    'application': False,
}