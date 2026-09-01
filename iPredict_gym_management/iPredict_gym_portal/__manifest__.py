# -*- coding: utf-8 -*-

{
    "name": "iPredict Gym Portal",
    "version": "19.0.1.0.0",
    "summary": "Gym Member Portal",
    "description": """
iPredict Gym Portal

Customer portal for gym members to view:
- Membership Details
- Assigned Trainer
- Workout Plans
- Exercises and Exercise Steps
- Diet Plans
- Meals
- Food and Nutrition Information
    """,
    "author": "iPredict IT Solutions",
    "website": "https://www.ipredictitsolutions.com",
    "category": "Services",
    "license": "LGPL-3",
    "depends": [
        "portal",
        "website",
        "iPredict_gym_base",
        "iPredict_gym_membership",
        "iPredict_gym_workout",
        "iPredict_gym_diet",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "iPredict_gym_portal/static/src/css/portal.css",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}