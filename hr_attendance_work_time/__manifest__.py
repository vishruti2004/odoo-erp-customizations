# -*- coding: utf-8 -*-
{
    "name": "HR Attendance Work Hours Without Break",
    "summary": "Adds Work Hours Without Break field and updates Worked Time to reflect raw attendance duration",
 
    "description": """
        This module extends Odoo 19 HR Attendance to separate raw attendance
        duration from break-adjusted duration.
 
        Features:
        - New Work Hours Without Break field on Attendance records
        - Worked Time field updated to show raw Check In / Check Out duration
        - Preserves the existing break-deducted calculation under the new field
    """,

    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "http://ipredictitsolutions.com",
    "support": "ipredictitsolutions@gmail.com",

    "category": "Point of Sale",
    "version": "19.0.1.0.0",

    "depends": [
        "point_of_sale",
        "pos_restaurant",
    ],

    "data": [  
        "views/hr_attandance_views.xml",   
    ],

    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}