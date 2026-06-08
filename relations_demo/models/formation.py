from odoo import models, fields, api


class Formation(models.Model):
    _name = 'formation'
    _description = 'Formation'

    name = fields.Char(string='Titre', required=True)
    date_start = fields.Date(string='Date de début')
    date_end = fields.Date(string='Date de fin')
    participant_ids = fields.Many2many(
        'res.users',
        string='Participants',
    )
    participant_count = fields.Integer(
        string='Nombre de participants',
        compute='_compute_participant_count',
        store=True,
    )
    session_ids = fields.One2many(
        'formation.session',
        'formation_id',
        string='Sessions',
        ondelete='cascade',
    )
    session_count = fields.Integer(
        string='Nombre de sessions',
        compute='_compute_session_count',
        store=True,
    )
    competence_ids = fields.Many2many(
        'formation.competence',
        string='Compétences',
    )

    @api.depends('participant_ids')
    def _compute_participant_count(self):
        for rec in self:
            rec.participant_count = len(rec.participant_ids)

    @api.depends('session_ids')
    def _compute_session_count(self):
        for rec in self:
            rec.session_count = len(rec.session_ids)


class FormationSession(models.Model):
    _name = 'formation.session'
    _description = 'Session de formation'
    _order = 'date'

    name = fields.Char(string='Titre', required=True)
    formation_id = fields.Many2one('formation', string='Formation', required=True, ondelete='cascade')
    date = fields.Date(string='Date', required=True)
    duration = fields.Float(string='Durée (h)', default=2.0)
    trainer_id = fields.Many2one('res.users', string='Formateur')
    note = fields.Text(string='Notes')


class FormationCompetence(models.Model):
    _name = 'formation.competence'
    _description = 'Compétence'

    name = fields.Char(string='Nom', required=True)
    level = fields.Selection([
        ('beginner', 'Débutant'),
        ('intermediate', 'Intermédiaire'),
        ('advanced', 'Avancé'),
    ], string='Niveau', default='beginner')
