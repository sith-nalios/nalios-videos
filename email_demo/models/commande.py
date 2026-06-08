from odoo import models, fields, api
from odoo.exceptions import UserError


class EmailCommande(models.Model):
    _name = 'email.commande'
    _description = 'Commande Demo Email'
    _inherit = ['mail.thread']

    name = fields.Char(string='Référence', required=True)
    client_email = fields.Char(string='Email client', required=True)
    client_name = fields.Char(string='Nom du client', required=True)
    montant = fields.Float(string='Montant (€)')
    state = fields.Selection([
        ('draft', 'Brouillon'),
        ('confirmed', 'Confirmée'),
        ('sent', 'Email envoyé'),
    ], string='Statut', default='draft', tracking=True)
    date_confirmation = fields.Datetime(string='Date de confirmation')

    def action_confirm(self):
        self.write({
            'state': 'confirmed',
            'date_confirmation': fields.Datetime.now(),
        })

    def action_send_confirmation_email(self):
        template = self.env.ref('email_demo.mail_template_commande_confirmation', raise_if_not_found=False)
        if not template:
            raise UserError("Le template d'email est introuvable.")
        for rec in self:
            template.send_mail(rec.id, force_send=True)
            rec.state = 'sent'

    def action_send_email_simple(self):
        for rec in self:
            self.env['mail.mail'].create({
                'subject': f'Votre commande {rec.name} a été reçue',
                'email_to': rec.client_email,
                'body_html': f'<p>Bonjour {rec.client_name},</p><p>Votre commande <b>{rec.name}</b> d\'un montant de <b>{rec.montant} €</b> a bien été reçue.</p>',
            }).send()
