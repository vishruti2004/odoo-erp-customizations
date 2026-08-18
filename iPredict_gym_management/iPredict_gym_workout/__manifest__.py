# -*- coding: utf-8 -*-
{
    "name": "iPredict Gym Workout",
    "version": "19.0.1.0.0",
    "summary": "Manage workout templates, exercise lists, and assign workout plans to members.",
    "description": """
iPredict Gym Workout

This module manages gym workout plans including:

- Workout Templates (with exercise lines)
- Assign Workout Plans to Members
- Track Workout Plan Status (Active, Paused, Completed)
- Trainer Assignment for Workout Plans
    """,
    "author": "iPredict IT Solutions",
    "website": "https://www.ipredictitsolutions.com",
    "category": "Services",
    "license": "LGPL-3",
    "depends": [
        "base",
        "contacts",
        "hr",
        "mail",
        "resource",
        "iPredict_gym_base",
        "iPredict_gym_membership",
    ],
    "data": [
        # Security
        "security/ir.model.access.csv",
        "security/security.xml",


        # Data
        "data/gym_sequence.xml",
        "data/ir_cron_data.xml",

        # Views
        "views/gym_exercise_views.xml",
        "views/gym_workout_plan_views.xml",
        "views/res_partner_views.xml",
        "views/gym_workout_assignment_views.xml",
        "views/menu_views.xml",

        "wizard/gym_workout_plan_assign_wizard_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}