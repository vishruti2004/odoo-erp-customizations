# -*- coding: utf-8 -*-
{
    'name': 'Contact Announcement',
    'version': '19.0.1.0.0',
    'summary': 'Manage and display announcements on Contact/Customer forms',
    'category': 'Contacts',
    'author': 'vishruti malaviya',

    'depends': [
        'base',
        'contacts',
        'mail',
        'portal',
        'website',
        'bus',
    ],

    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',

        'data/cron.xml',
        'data/mail_template.xml',

        'views/contact_announcement_views.xml',
        'views/res_partner_views.xml',
        'views/portal_templates.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'contact_announcement/static/src/js/notification.js',
        ],
        'web.assets_frontend': [
            'contact_announcement/static/src/js/portal_bus_service.js',
            'contact_announcement/static/src/xml/announcement_template.xml',
        ],
   
},

    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}