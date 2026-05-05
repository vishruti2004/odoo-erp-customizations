{
    'name': 'Hr management',
    'version': '1.0',
    'category': 'hr/attandance',
    'summary': 'hr management',
    'depends': ['hr_attendance', 'web'],
    "sequence": -100,
    "author": "vishruti malaviya",
    "license": "LGPL-3",
    'data': [

        'data/mail_template.xml',

        'views/res_config_settings_views.xml',
        'views/hr_leave_type_views.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'hr_management/static/src/js/attendance_check.js',
        ],
    },
    'installable': True,
    'application': False,
}