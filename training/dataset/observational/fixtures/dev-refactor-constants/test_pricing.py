import unittest
import pricing
class T(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(pricing.UNIT_PRICE,9.99)
        self.assertEqual(pricing.SHIPPING,5.00)
    def test_price(self):
        self.assertAlmostEqual(pricing.price(2),24.98)
if __name__=='__main__': unittest.main()
