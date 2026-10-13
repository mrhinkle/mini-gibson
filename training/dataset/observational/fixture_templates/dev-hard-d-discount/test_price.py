import unittest
from discount.price import final_price

class T(unittest.TestCase):
    def test_percent_only(self):
        self.assertEqual(final_price(200, 25, 0), 150)

    def test_fixed_only(self):
        self.assertEqual(final_price(200, 0, 50), 150)

    def test_order(self):
        self.assertEqual(final_price(1000, 10, 50), 850)

    def test_floor(self):
        self.assertEqual(final_price(100, 0, 500), 0)
