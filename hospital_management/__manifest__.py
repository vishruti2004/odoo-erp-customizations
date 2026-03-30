{
    "name": "Hospital Management System",
    "version": "19.0.1.0.0",
    "summary": "Hospital ERP",
    "author": "vishruti malaviya",
    "category": "Healthcare",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "account",
        "web",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "data/specialization_data.xml",
       
        "report/appointment_report.xml",
        "report/appointment_report_template.xml",
        "report/appointment_summary_report.xml",
        "report/appointment_summary_template.xml",

         "data/mail_template.xml",
        "data/ir_cron.xml",

        "views/patient_views.xml",
        "views/res_partner_views.xml",
        "views/doctor_views.xml",
        "views/specialization_views.xml",
        "views/appointment_views.xml",
        "views/dashboard_views.xml",
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
        "web.assets_frontend": [
            "hospital_management/static/src/css/portal.css",
        ],

        "web.assets_backend": [
            "hospital_management/static/src/services/dashboard_services.js",

            "hospital_management/static/src/js/ChartRender.js",

            "hospital_management/static/src/js/dashboard.js",
            "hospital_management/static/src/js/card.js",
            "hospital_management/static/src/js/Doctorlist.js",



            "hospital_management/static/src/xml/dashboard.xml",
            "hospital_management/static/src/xml/ChartRender.xml",
            "hospital_management/static/src/xml/card.xml",
            "hospital_management/static/src/xml/Doctorlist.xml",

            "hospital_management/static/src/css/dashboard.css",
        # "hospital_management/static/src/js/dashboard.js",
        # "hospital_management/static/src/js/counter.js",
        # "hospital_management/static/src/js/card.js",
        # "hospital_management/static/src/js/TodoItem.js",
        # "hospital_management/static/src/js/TodoList.js",


        # "hospital_management/static/src/xml/*.xml",

        ],

       
    },
    "installable": True,
    "application": True,
}
