from odoo import models, fields


class EdiFieldMapping(models.Model):
    _name = 'edi.field.mapping'
    _description = 'EDI Field Mapping'
    _order = 'sequence, id'

    profile_id = fields.Many2one('edi.profile', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    source_path = fields.Char(
        required=True,
        help="Chemin vers le tag XML (ex: RefCmd, Header/RefCmd, ./Header/RefCmd) ou @attribut"
    )
    odoo_field_id = fields.Many2one(
        'ir.model.fields', required=True, ondelete='cascade', string='Champ Odoo',
        domain="[('model_id', '=', parent.model_id), ('ttype', 'not in', ['one2many', 'many2many', 'binary'])]"
    )
    odoo_field_name = fields.Char(related='odoo_field_id.name', store=True)
    transformer = fields.Selection([
        ('none', 'Aucun'),
        ('date', 'Date (YYYY-MM-DD)'),
        ('date_dmy', 'Date (DD/MM/YYYY)'),
        ('float', 'Nombre décimal'),
        ('int', 'Entier'),
        ('bool', 'Booléen (true/1/yes)'),
        ('m2o_name', 'Many2one par nom'),
        ('m2o_ref', 'Many2one par référence'),
        ('python', 'Expression Python'),
    ], default='none', required=True)
    transform_code = fields.Char(
        string='Expression',
        help="Expression Python. Variable 'value' disponible. Ex: value.strip().upper()"
    )
    default_value = fields.Char(help="Valeur utilisée si le tag source est absent")
    is_key = fields.Boolean(string='Clé upsert', help="Utilisé pour identifier un enregistrement existant")
    m2o_search_field = fields.Char(
        string='Champ de recherche',
        help="Champ utilisé pour chercher le Many2one (ex: name, ref). Défaut: name"
    )
