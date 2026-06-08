from odoo import models, fields


class EdiActionRule(models.Model):
    _name = 'edi.action.rule'
    _description = "EDI Action Rule"
    _order = 'sequence, id'

    profile_id = fields.Many2one('edi.profile', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    action_type = fields.Selection([
        ('create', 'Créer'),
        ('update', 'Mettre à jour'),
        ('upsert', 'Créer ou mettre à jour'),
        ('call_method', 'Appeler méthode'),
        ('notify', 'Notification chatter'),
    ], required=True, default='upsert')
    method_name = fields.Char(help="Nom de la méthode à appeler sur le record (ex: action_confirm)")
    condition_code = fields.Char(
        string='Condition',
        help="Expression Python retournant True/False. Variables: 'values' (dict). Ex: values.get('state') == 'done'"
    )
