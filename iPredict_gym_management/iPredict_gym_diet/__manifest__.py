{
    'name': 'iPredict Gym Diet',
    'version': '19.0.1.0.0',
    'summary': 'Diet & Nutrition Management for Gym Members',
    'description': """
        iPredict Gym Diet
        =================
        Manage customized diet plans, meal schedules,
        nutritional recommendations, and calorie tracking.
    """,
    'author': 'iPredict IT Solutions',
    'depends': [
        'base',
        'contacts',
        'hr',
        'mail',
        'iPredict_gym_base',
        'iPredict_gym_membership',
    ],
    'data': [
        'security/ir.model.access.csv',

        'data/diet_plan_sequence.xml',
        'data/ir_cron_data.xml',           
        'views/gym_diet_plan_views.xml',
        'views/gym_food.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/diet_assignment_views.xml',
        'views/menu_views.xml',

        'wizard/gym_diet_plan_assign_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}