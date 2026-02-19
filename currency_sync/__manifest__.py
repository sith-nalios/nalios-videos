{
    'name': 'Currency Sync – Intégration API Externe',
    'version': '19.0.1.0.0',
    'summary': 'Récupère les taux de change depuis une API externe',
    'author': 'Nalios',
    'category': 'Accounting',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/currency_rate_external_views.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
