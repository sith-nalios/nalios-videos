{
    'name': 'Email Demo – Envoyer des emails depuis Python',
    'version': '19.0.1.0.0',
    'summary': 'Démonstration de mail.template et send_mail() pour envoyer des emails depuis un module custom',
    'author': 'Nalios',
    'category': 'Tools',
    'depends': ['mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template.xml',
        'views/commande_views.xml',
    ],
    'installable': True,
    'license': 'LGPL-3',
}
