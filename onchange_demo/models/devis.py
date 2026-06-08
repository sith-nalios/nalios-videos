from odoo import models, fields, api


class Devis(models.Model):
    _name = 'onchange.devis'
    _description = 'Devis Demo Onchange'

    name = fields.Char(string='Référence', required=True)
    client_type = fields.Selection([
        ('particulier', 'Particulier'),
        ('professionnel', 'Professionnel'),
        ('vip', 'VIP'),
    ], string='Type de client', default='particulier')
    remise = fields.Float(string='Remise (%)', default=0.0)
    montant_ht = fields.Float(string='Montant HT (€)')
    tva = fields.Float(string='TVA (%)', default=20.0)
    montant_ttc = fields.Float(string='Montant TTC (€)', compute='_compute_ttc', store=True)
    note = fields.Text(string='Note interne')
    warning_message = fields.Char(string='Avertissement', readonly=True)

    @api.onchange('client_type')
    def _onchange_client_type(self):
        if self.client_type == 'vip':
            self.remise = 20.0
            self.warning_message = 'Client VIP : remise de 20% appliquée automatiquement.'
        elif self.client_type == 'professionnel':
            self.remise = 10.0
            self.warning_message = 'Client professionnel : remise de 10% appliquée.'
        else:
            self.remise = 0.0
            self.warning_message = ''

    @api.onchange('remise')
    def _onchange_remise(self):
        if self.remise > 30.0:
            self.remise = 30.0
            return {
                'warning': {
                    'title': 'Remise trop élevée',
                    'message': 'La remise maximale autorisée est de 30%. Valeur ramenée à 30%.',
                }
            }

    @api.onchange('montant_ht', 'remise')
    def _onchange_montant(self):
        if self.montant_ht < 0:
            self.montant_ht = 0.0

    @api.depends('montant_ht', 'tva', 'remise')
    def _compute_ttc(self):
        for rec in self:
            base = rec.montant_ht * (1 - rec.remise / 100)
            rec.montant_ttc = base * (1 + rec.tva / 100)
