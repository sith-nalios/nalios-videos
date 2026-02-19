from odoo.tests.common import TransactionCase


class TestSaleOrder(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Client Test'})
        self.product = self.env['product.product'].create({
            'name': 'Produit Test',
            'list_price': 50.0,
            'type': 'consu',
        })
        self.order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2,
                'price_unit': 50.0,
            })],
        })

    def test_order_total(self):
        self.assertEqual(self.order.amount_untaxed, 100.0)

    def test_order_line_count(self):
        self.assertEqual(len(self.order.order_line), 1)

    def test_order_confirm(self):
        self.order.action_confirm()
        self.assertEqual(self.order.state, 'sale')

    def test_order_total_after_add_line(self):
        self.env['sale.order.line'].create({
            'order_id': self.order.id,
            'product_id': self.product.id,
            'product_uom_qty': 3,
            'price_unit': 50.0,
        })
        self.assertEqual(self.order.amount_untaxed, 250.0)
