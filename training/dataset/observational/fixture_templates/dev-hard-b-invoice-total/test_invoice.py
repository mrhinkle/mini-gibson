import unittest
from orders.invoice import grand

class T(unittest.TestCase):
    def test_bulk_at_threshold(self):
        got = grand([(10, 100)], 0)
        self.assertEqual(got, {"subtotal": 900, "tax": 0, "total": 900})

    def test_below_bulk(self):
        got = grand([(9, 100)], 0)
        self.assertEqual(got, {"subtotal": 900, "tax": 0, "total": 900})

    def test_tax_rate(self):
        got = grand([(1, 100)], 1000)
        self.assertEqual(got, {"subtotal": 100, "tax": 10, "total": 110})

    def test_zero_tax(self):
        got = grand([(1, 100)], 0)
        self.assertEqual(got, {"subtotal": 100, "tax": 0, "total": 100})
