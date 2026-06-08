{
    'name': 'Inherits Demo – Les 3 types d\'héritage Odoo',
    'version': '19.0.1.0.0',
    'summary': 'Démonstration de _inherit (extension), _inherit+_name (prototype) et _inherits (délégation)',
    'author': 'Nalios',
    'category': 'Tools',
    'depends': ['base', 'mail', 'calendar'],
    'data': [
        'security/ir.model.access.csv',
        'views/employe_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
