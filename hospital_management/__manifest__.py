# -*- coding: utf-8 -*-
{
    "name": "Hospital Management System",
    "version": "19.0.1.0.0",
    "summary": "Hospital ERP with Dynamic Website Snippets",
    "sequence": -100,
    "author": "vishruti malaviya",
    "category": "Healthcare",
    "license": "LGPL-3",
    "website": "www.yourhospital.com",
    "depends": [
        "hr", 
        "account", 
        "website", 
        "web",
        "html_builder"
    ],
    "data": [
        # Security
        "security/security.xml",
        "security/ir.model.access.csv",
        
        # Data
        "data/ir_sequence_data.xml",
        "data/specialization_data.xml",
        "data/mail_template.xml",
        "data/ir_cron.xml",
        
        # Reports
        "report/appointment_report.xml",
        "report/appointment_report_template.xml",
        "report/appointment_summary_report.xml",
        "report/appointment_summary_template.xml",
        
        # Views
        "views/patient_views.xml",
        "views/res_partner_views.xml",
        "views/doctor_views.xml",
        "views/specialization_views.xml",
        "views/appointment_views.xml",
        "views/dashboard_views.xml",
        "views/res_config_settings_view.xml",
        
        # Portal Templates
        "views/portal_home_templates.xml",
        "views/portal_appointments_templates.xml",
        "views/portal_appointments_details_templates.xml",
        "views/portal_appointments_add_templates.xml",
        
        # Snippets
        "views/snippets/s_doctor_list.xml",
        "views/snippets/snippets.xml",
        
        # Wizards
        "wizard/appointment_cancel_wizard_view.xml",
        "wizard/appointment_summary_wizard_view.xml",
    ],
    "assets": {
   
        "website.assets_wysiwyg": [
            "hospital_management/static/src/js/s_doctor_list_option.js",
            "hospital_management/static/src/xml/s_doctor_snippet_options.xml",
        ],
    
        "web.assets_frontend": [
            "hospital_management/static/src/scss/doctor_list.scss",
            "hospital_management/static/src/js/s_doctor_list.js",
            "hospital_management/static/src/css/portal.css",
        ],
        
        "web.assets_backend": [
            "hospital_management/static/src/css/dashboard.css",
            "hospital_management/static/src/services/dashboard_services.js",
            "hospital_management/static/src/js/ChartRender.js",
            "hospital_management/static/src/js/card.js",
            "hospital_management/static/src/js/Doctorlist.js",
            "hospital_management/static/src/js/dashboard.js",
            "hospital_management/static/src/xml/dashboard.xml",
            "hospital_management/static/src/xml/ChartRender.xml",
            "hospital_management/static/src/xml/card.xml",
            "hospital_management/static/src/xml/Doctorlist.xml",
        ],
        
        "web.report_assets_common": [
            "hospital_management/static/src/css/appointment_report.css",
            "hospital_management/static/src/css/appointment_summary_report.css",
        ],
    },
    "installable": True,
    "application": True,
    "auto_install": False,
}