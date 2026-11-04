{
    "name": "Contact Approval Workflow",
    'summary': 'Contact Approval workflow',
    "description": "This module will allows you to approve or Reject Contact (Customer/Supplier) only by Contact Manager.",

    'author': 'iPredict IT Solutions Pvt. Ltd.',
    'website': 'http://ipredictitsolutions.com',
    "support": "ipredictitsolutions@gmail.com",

    "version": "19.0.1.0.0",
    "category": "Extra Tools",
    "depends": ['contacts', 'mail'],

    "data": [
        'security/res_partner_security.xml',
        'security/ir.model.access.csv',
        'data/customer_approval_mail_template.xml',
        'data/partner_server_action.xml',
        'views/partner_view.xml',
        'wizard/contact_approval_wizard_views.xml',
    ],

    "assets": {
        "web.assets_backend": [
            'customer_approval_workflow/static/src/js/many2one_patch.js',
         ],
    },

    'license': "OPL-1",
    "installable": True,

}