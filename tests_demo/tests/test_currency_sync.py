from unittest.mock import patch
from odoo.tests.common import TransactionCase


MOCK_API_RESPONSE = {
    'result': 'success',
    'base_code': 'EUR',
    'rates': {
        'USD': 1.08,
        'CAD': 1.47,
        'GBP': 0.85,
    }
}


class TestCurrencySync(TransactionCase):

    def setUp(self):
        super().setUp()
        self.usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        if not self.usd:
            self.usd = self.env['res.currency'].create({'name': 'USD', 'symbol': '$'})

    @patch('requests.get')
    def test_sync_cree_enregistrement(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_API_RESPONSE
        mock_get.return_value.raise_for_status.return_value = None

        self.env['res.currency.rate.external'].action_sync_rates()

        record = self.env['res.currency.rate.external'].search([
            ('currency_id', '=', self.usd.id)
        ], limit=1)
        self.assertTrue(record, "Un enregistrement USD doit être créé")
        self.assertAlmostEqual(record.rate, 1.08, places=2)

    @patch('requests.get')
    def test_sync_met_a_jour_existant(self, mock_get):
        mock_get.return_value.json.return_value = MOCK_API_RESPONSE
        mock_get.return_value.raise_for_status.return_value = None

        self.env['res.currency.rate.external'].action_sync_rates()
        self.env['res.currency.rate.external'].action_sync_rates()

        records = self.env['res.currency.rate.external'].search([
            ('currency_id', '=', self.usd.id)
        ])
        self.assertEqual(len(records), 1, "Il ne doit y avoir qu'un seul enregistrement par devise")

    @patch('requests.get')
    def test_sync_erreur_api(self, mock_get):
        mock_get.side_effect = Exception("Timeout")

        with self.assertRaises(Exception):
            self.env['res.currency.rate.external'].action_sync_rates()
