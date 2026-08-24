# -*- coding: utf-8 -*-
{
    'name': 'Attendance: allow to capture image on check in/out',
    'summary': 'Attendance: allow to capture image on check in/out',
    'description': """Attendance: allow to capture image on check in/out""",

    'author': 'iPredict IT Solutions Pvt. Ltd.',
    'website': 'http://ipredictitsolutions.com',
    'support': 'ipredictitsolutions@gmail.com',

    'category': 'Human Resources/Attendances',
    'version': '19.0.0.0.1',
    'depends': ['hr_attendance'],

    'external_dependencies': {
        'python': [
            'face_recognition',
            'cv2',
            'onnxruntime',
        ],
    },

    'data': [
        'security/ir.model.access.csv',
        'views/hr_attendance_views.xml',
        'views/res_config_views.xml',
        'views/hr_employee_views.xml',
        'views/res_users_views.xml',
        'views/face_attendance_location_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'hr_attendance_image/static/src/**/*',
        ],
        'hr_attendance.assets_public_attendance': [
            "hr_attendance_image/static/src/public_kiosk/**/*",
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
