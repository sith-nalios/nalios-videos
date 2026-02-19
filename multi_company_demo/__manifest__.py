{
    'name': 'Multi-Company Demo – Règles d\'accès par société',
    'version': '19.0.1.0.0',
    'summary': 'Démonstration du multi-company et des règles d\'accès ir.rule',
    'author': 'Nalios',
    'category': 'Tools',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'views/company_document_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
