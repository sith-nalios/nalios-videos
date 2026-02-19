from odoo.tests.common import TransactionCase


class TestProduct(TransactionCase):

    def setUp(self):
        super().setUp()
        self.product = self.env['product.template'].create({
            'name': 'Produit Test',
            'list_price': 100.0,
            'type': 'consu',
        })

    def test_product_name(self):
        self.assertEqual(self.product.name, 'Produit Test')

    def test_product_price(self):
        self.assertEqual(self.product.list_price, 100.0)

    def test_product_price_update(self):
        self.product.list_price = 150.0
        self.assertEqual(self.product.list_price, 150.0)
