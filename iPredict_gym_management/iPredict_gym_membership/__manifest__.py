# -*- coding: utf-8 -*-
{
    "name": "iPredict Gym Membership",
    "version": "19.0.1.0.0",
    "summary": "Manage gym memberships, membership plans, trial sessions, member measurements, and feedback.",
    "description": """
iPredict Gym Membership

This module manages the complete membership lifecycle including:

- Membership Plans
- Member Registration
- Membership Renewal
- Membership History
- Trial Sessions
- Body Measurements
- Member Feedback
- CRM Lead Integration
    """,
    "author": "iPredict IT Solutions",
    "website": "https://www.ipredictitsolutions.com",
    "category": "Services",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "crm",
        "sale",
        "mail",
        "product",
        "resource",
        "iPredict_gym_base",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",

        # Data
        "data/mail_template.xml",
        'data/gym_sequence.xml',
        "data/cron.xml",


        # Views
        "views/gym_members_views.xml",
        "views/gym_membership_plan_views.xml",
        "views/res_partner_views.xml",
        "views/hr_employee_views.xml",
        "views/gym_membership_freeze.xml",
        "views/gym_frozen_members.xml",

        "views/menu_views.xml",

    ],
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}