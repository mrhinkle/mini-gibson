import unittest

from math_helpers import factorial


class FactorialTests(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(factorial(0), 1)

    def test_positive(self):
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)

    def test_negative(self):
        with self.assertRaises(ValueError):
            factorial(-1)


if __name__ == "__main__":
    unittest.main()
