from odoo import models, fields


# ── TYPE 1 : _inherit seul ──────────────────────────────────────────────────
class ResPartnerExtended(models.Model):
    _inherit = 'res.partner'

    nalios_client_level = fields.Selection([
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
    ], string='Niveau client Nalios', default='bronze')
    nalios_note = fields.Text(string='Note Nalios')


# ── TYPE 2 : _inherit + _name ──────────────────────────────────────────────
class PresseContact(models.Model):
    _name = 'inherits.presse.contact'
    _description = 'Contact Presse (prototype de res.partner)'
    _inherit = 'res.partner'

    category_id = fields.Many2many('res.partner.category', 'presse_contact_category_rel', 'partner_id', 'category_id', string='Tags')
    channel_ids = fields.Many2many('discuss.channel', 'presse_contact_channel_rel', 'partner_id', 'channel_id', string='Channels')
    meeting_ids = fields.Many2many('calendar.event', 'presse_contact_meeting_rel', 'partner_id', 'event_id', string='Réunions')
    commercial_partner_id = fields.Many2one('inherits.presse.contact', compute='_compute_commercial_partner', store=True, string='Entité commerciale')
    partner_share = fields.Boolean('Share Partner', compute='_compute_partner_share_presse', store=True)
    media = fields.Char(string='Média')
    rubrique = fields.Char(string='Rubrique')

    def _compute_partner_share_presse(self):
        for partner in self:
            partner.partner_share = not partner.user_ids or not any(not user.share for user in partner.user_ids)


# ── TYPE 3 : _inherits ────────────────────────────────────────────────────
class InheritsEmploye(models.Model):
    _name = 'inherits.employe'
    _description = 'Employé (délégation vers res.partner)'
    _inherits = {'res.partner': 'partner_id'}

    partner_id = fields.Many2one('res.partner', delegate=True, required=True, ondelete='cascade', string='Contact lié')
    matricule = fields.Char(string='Matricule', required=True)
    poste = fields.Char(string='Poste')
    date_embauche = fields.Date(string='Date d\'embauche', default=fields.Date.today)
    salaire = fields.Float(string='Salaire mensuel (€)')
