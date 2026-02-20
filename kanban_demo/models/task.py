from odoo import models, fields, api


class KanbanTask(models.Model):
    _name = 'kanban.task'
    _description = 'Tâche Kanban'
    _order = 'sequence, id'

    name = fields.Char(string='Titre', required=True)
    description = fields.Text(string='Description')
    sequence = fields.Integer(string='Séquence', default=10)
    user_id = fields.Many2one('res.users', string='Assigné à', default=lambda self: self.env.user)
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Urgent'),
    ], string='Priorité', default='0')
    state = fields.Selection([
        ('todo', 'À faire'),
        ('in_progress', 'En cours'),
        ('done', 'Terminé'),
        ('cancelled', 'Annulé'),
    ], string='Statut', default='todo', group_expand='_expand_states')
    progress = fields.Integer(string='Progression (%)', default=0)
    color = fields.Integer(string='Couleur')
    tag_ids = fields.Many2many('kanban.tag', string='Tags')

    @api.model
    def _expand_states(self, values, domain):
        return [key for key, _ in self._fields['state'].selection]

    def action_set_in_progress(self):
        self.write({'state': 'in_progress', 'progress': 50})

    def action_set_done(self):
        self.write({'state': 'done', 'progress': 100})


class KanbanTag(models.Model):
    _name = 'kanban.tag'
    _description = 'Tag Kanban'

    name = fields.Char(string='Nom', required=True)
    color = fields.Integer(string='Couleur')
