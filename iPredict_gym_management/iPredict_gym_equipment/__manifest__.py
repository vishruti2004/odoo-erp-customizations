# -*- coding: utf-8 -*-
{
    "name": "iPredict Gym Equipment",
    "version": "19.0.1.0.0",
    "summary": "Manage gym equipment, maintenance, repair cost and spare parts using Odoo's native Maintenance module.",
    "description": """
iPredict Gym Equipment

Reuses Odoo's native Maintenance module for:
- Equipment master data (purchase, vendor, warranty, serial number)
- Preventive maintenance (AMC) scheduling
- Corrective maintenance (breakdown/repair requests)
- MTBF / MTTR statistics

Adds only what's missing:
- Repair Cost tracking
- Spare Parts usage tracking
    """,
    "author": "iPredict IT Solutions",
    "website": "https://www.ipredictitsolutions.com",
    "category": "Services",
    "license": "LGPL-3",
    "depends": [
        "base",
        "maintenance",
        'repair',
        "iPredict_gym_base",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/equipment_views.xml",
        "views/repair_views.xml",
        "views/maintenance_request.xml",
        "views/menu_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}