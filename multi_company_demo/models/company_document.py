from odoo import models, fields


class CompanyDocument(models.Model):
    _name = 'company.document'
    _description = 'Document par société'

    name = fields.Char(string='Titre', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Société',
        required=True,
        default=lambda self: self.env.company,
    )
    content = fields.Text(string='Contenu')
    date = fields.Date(string='Date', default=fields.Date.today)
