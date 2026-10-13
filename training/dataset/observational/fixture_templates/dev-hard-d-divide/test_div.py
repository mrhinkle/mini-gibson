import unittest
from arith.div import divide

class T(unittest.TestCase):
    def test_half(self):
        self.assertEqual(divide(7, 2), 3.5)

    def test_negative(self):
        self.assertEqual(divide(-4, 2), -2)

    def test_zero(self):
        with self.assertRaises(ValueError) as ctx:
            divide(1, 0)
        self.assertIn("division by zero", str(ctx.exception))
