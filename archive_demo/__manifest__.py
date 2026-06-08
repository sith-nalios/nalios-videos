{
    'name': 'Archive Demo – Champ active et archivage',
    'version': '19.0.1.0.0',
    'summary': 'Démonstration du champ active pour archiver/désarchiver des enregistrements dans Odoo',
    'author': 'Nalios',
    'category': 'Tools',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/produit_views.xml',
        'data/demo_data.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
