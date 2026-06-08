from odoo import models, fields


class PivotVente(models.Model):
    _name = 'pivot.vente'
    _description = 'Vente Demo Pivot'

    name = fields.Char(string='Référence', required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.today)
    vendeur = fields.Selection([
        ('alice', 'Alice'),
        ('bob', 'Bob'),
        ('charlie', 'Charlie'),
    ], string='Vendeur', required=True)
    categorie = fields.Selection([
        ('informatique', 'Informatique'),
        ('mobilier', 'Mobilier'),
        ('fourniture', 'Fourniture'),
    ], string='Catégorie', required=True)
    region = fields.Selection([
        ('nord', 'Nord'),
        ('sud', 'Sud'),
        ('est', 'Est'),
        ('ouest', 'Ouest'),
    ], string='Région', required=True)
    quantite = fields.Integer(string='Quantité', default=1)
    prix_unitaire = fields.Float(string='Prix unitaire (€)')
    montant_total = fields.Float(string='Montant total (€)', compute='_compute_total', store=True)

    def _compute_total(self):
        for rec in self:
            rec.montant_total = rec.quantite * rec.prix_unitaire
