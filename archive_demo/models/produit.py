from odoo import models, fields, api
from odoo.exceptions import UserError


class ArchiveProduit(models.Model):
    _name = 'archive.produit'
    _description = 'Produit Demo Archive'

    name = fields.Char(string='Nom du produit', required=True)
    active = fields.Boolean(string='Actif', default=True)
    categorie = fields.Selection([
        ('electronique', 'Électronique'),
        ('vetement', 'Vêtement'),
        ('alimentaire', 'Alimentaire'),
    ], string='Catégorie', required=True)
    stock = fields.Integer(string='Stock disponible', default=0)
    prix = fields.Float(string='Prix (€)')
    date_creation = fields.Date(string='Date de création', default=fields.Date.today)
    date_archivage = fields.Datetime(string='Date d\'archivage', readonly=True)

    @api.model
    def _get_archived_count(self):
        return self.with_context(active_test=False).search_count([('active', '=', False)])

    def action_archive_if_no_stock(self):
        for rec in self:
            if rec.stock > 0:
                raise UserError(f"Le produit '{rec.name}' a encore {rec.stock} unités en stock. Videz le stock avant d'archiver.")
            rec.active = False
            rec.date_archivage = fields.Datetime.now()

    def action_restore(self):
        self.write({'active': True, 'date_archivage': False})
