import requests
from odoo import models, fields, api
from odoo.exceptions import UserError


class CurrencyRateExternal(models.Model):
    _name = 'res.currency.rate.external'
    _description = 'Taux de change externe'
    _order = 'date desc'

    currency_id = fields.Many2one('res.currency', string='Devise', required=True)
    rate = fields.Float(string='Taux', digits=(12, 6))
    date = fields.Datetime(string='Date', default=fields.Datetime.now)

    def _sync(self, rates):
        for currency in self.env['res.currency'].search([]):
            if currency.name in rates:
                existing = self.search([('currency_id', '=', currency.id)], limit=1)
                if existing:
                    existing.write({
                        'rate': rates[currency.name],
                        'date': fields.Datetime.now(),
                    })
                else:
                    self.create({
                        'currency_id': currency.id,
                        'rate': rates[currency.name],
                        'date': fields.Datetime.now(),
                    })

    @api.model
    def action_sync_rates(self):
        url = 'https://open.er-api.com/v6/latest/USD'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            raise UserError(f'Erreur lors de l\'appel API : {e}')
        self._sync(data.get('rates', {}))

    @api.model
    def cron_sync_rates(self):
        url = 'https://open.er-api.com/v6/latest/USD'
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return
        self._sync(data.get('rates', {}))
