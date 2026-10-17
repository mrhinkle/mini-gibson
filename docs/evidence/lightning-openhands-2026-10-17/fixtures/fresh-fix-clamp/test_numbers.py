import unittest

from bounds import clamp


class ClampTests(unittest.TestCase):
    def test_inside_range(self):
        self.assertEqual(clamp(5, 1, 10), 5)

    def test_below_range(self):
        self.assertEqual(clamp(-2, 1, 10), 1)

    def test_above_range(self):
        self.assertEqual(clamp(12, 1, 10), 10)

    def test_invalid_range(self):
        with self.assertRaises(ValueError):
            clamp(1, 3, 2)


if __name__ == "__main__":
    unittest.main()
