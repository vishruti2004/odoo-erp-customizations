# -*- coding: utf-8 -*-

{
    "name": "Advanced Chatter",
    "version": "19.0.1.0.0",
    "summary": "Advanced Chatter Search, Filter and Export",
    "description": """
Advanced Chatter - Search, Filter and Export

Features:

- Advanced Chatter Search
- Search Chatter messages using keywords
- Filter messages by Date, User, Model, Record and Message Type
- Search and filter Chatter Activities
- Apply multiple filters simultaneously
- Display filtered Chatter results
- Export filtered search results
    """,
    "category": "Discuss/Chatter",
    "author": "iPredict IT Solutions Pvt. Ltd.",
    "website": "https://ipredictitsolutions.com",
    "license": "LGPL-3",

    "depends": [
        "base",
        "mail",
        "web",
    ],

    # "data": [
    #     "security/ir.model.access.csv",
    # ],

    "assets": {
        "web.assets_backend": [
            "advanced_chatter/static/src/js/advanced_chatter.js",
            "advanced_chatter/static/src/xml/advanced_chatter.xml",
            "advanced_chatter/static/src/css/advanced_chatter.css",
        ],
    },

    "images": [
        "static/description/icon.png",
    ],

    "demo": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}