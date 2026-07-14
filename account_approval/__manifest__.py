# -*- coding: utf-8 -*-
{
    "name": "Invoice Approval Workflow",
    "summary": "Multi-level invoice approval workflow with rules, history and email notifications",

    "description": """
        Invoice Approval Workflow for Odoo 19 Accounting.
        
        Features:
        - Configurable approval rules based on amount, invoice type, company
        - Single or Multi-level approval
        - Submit, Approve, Reject buttons on invoice form
        - Approval history tracking
        - Email notifications to approvers
        - Auto-post invoice after final approval
        - Manager comments support
        - Chatter integration
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Tools",
    "version": "19.0.1.0.0",

    "depends": [
        "account",
        "mail",
    ],

    "data": [
        # Security
        # "security/account_approval_security.xml",
        "security/ir.model.access.csv",
        
        # Data
        "data/mail_template.xml",
        
        # # Views
        "views/account_approval_rule_views.xml",
        "views/account_approval_menu.xml",
        "views/account_move_views.xml",
        "views/account_approval_comment_wizard_views.xml",
        
    ],

    "license": "LGPL-3",

    "installable": True,
    "application": False,
    "auto_install": False,
}