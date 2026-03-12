{
    "name": "Hospital Management System",
    "version": "19.0.1.0.0",
    "summary": "Hospital ERP",
    "author": "vishruti malaviya",
    "category": "Healthcare",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "hr",
        "portal",
        "account",
    ],
    "data": [


        "security/security.xml",
        "security/ir.model.access.csv",

        "data/ir_sequence_data.xml",
        "data/specialization_data.xml",
        "data/mail_template.xml",
        "data/reminder_patient_mail.xml",
        "data/birthday_doctor_mail.xml",
        "data/ir_cron.xml",

        "report/appointment_report.xml",
        "report/appointment_report_template.xml",
        "report/appointment_summary_report.xml",
        "report/appointment_summary_template.xml",

        "views/patient_views.xml",
        "views/res_partner_views.xml",
        "views/doctor_views.xml",
        "views/specialization_views.xml",
        "views/appointment_views.xml",
        "views/res_config_settings_view.xml",

        "views/portal_appointments_templates.xml",
        "views/portal_home_templates.xml",
        "views/portal_appointments_details_templates.xml",
        "views/portal_appointments_add_templates.xml",



        "wizard/appointment_cancel_wizard_view.xml",
        "wizard/appointment_summary_wizard_view.xml",
    ],
        

    "assets": {
        "web.report_assets_common": [
            "hospital_management/static/src/css/appointment_report.css",
            "hospital_management/static/src/css/appointment_summary_report.css",

        ],

        "web.assets_frontend":[
                    'hospital_management/static/src/css/portal.css',

        ],
    },

    "installable": True,
    "application": True,
}